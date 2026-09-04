"""Shared helpers for both the daily Shorts and the weekly long-form
compilation: font lookup, background palettes, natural neural-voice TTS,
and ffmpeg muxing/concatenation.

Voice strategy:
- English (daily Shorts only): ElevenLabs when ELEVENLABS_API_KEY is set,
  falling back to edge-tts on any failure. Paid credits are spent only here.
- Korean: always edge-tts.
- Compilations (weekly / mega): always edge-tts. One mega run narrates
  ~240 segments, which would drain a month of credits in a single job, so
  those callers pass use_elevenlabs_for_en=False explicitly.

edge-tts (Microsoft neural voices) stays the floor everywhere: free,
unlimited, no API key, nothing to rotate or run out of.
"""

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1920

# A few tonal variants of the same navy/teal brand family so videos aren't
# pixel-identical (avoids the "obviously templated" look) while staying
# clearly recognizable as the same channel.
PALETTES = [
    ((18, 38, 68), (10, 58, 56)),    # navy -> teal (primary)
    ((28, 24, 58), (12, 46, 58)),    # indigo -> teal
    ((16, 44, 40), (36, 30, 12)),    # deep teal -> warm bronze accent
]

# edge-tts voices (free, unlimited, no API key)
EDGE_VOICE_EN = "en-US-GuyNeural"
EDGE_VOICE_KO = "ko-KR-InJoonNeural"

# ElevenLabs — English narration on the daily Shorts. Override the voice with
# ELEVENLABS_VOICE_ID; without it the premade "Adam" voice is used.
ELEVENLABS_DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # "Adam", a premade voice
ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
]


def find_korean_font() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise SystemExit(
        "No Korean-capable font found. Install one, e.g.:\n"
        "  sudo apt-get install -y fonts-noto-cjk\n"
        "or fonts-nanum, then re-run."
    )


def pick_palette(seed: str):
    return PALETTES[hash(seed) % len(PALETTES)]


def make_background(top_color, bottom_color) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), top_color)
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))
    return img


def draw_centered(draw, text, font, y, fill, wrap_width, line_gap=16, canvas_width=WIDTH):
    wrapped = textwrap.fill(text, width=wrap_width)
    lines = wrapped.split("\n")
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (canvas_width - line_w) / 2
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=fill)
        y += (bbox[3] - bbox[1]) + line_gap
    return y




def tts_save_elevenlabs(text: str, out_path: Path) -> None:
    api_key = os.environ["ELEVENLABS_API_KEY"]
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", ELEVENLABS_DEFAULT_VOICE_ID)
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": text,
            "model_id": ELEVENLABS_MODEL_ID,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=30,
    )
    resp.raise_for_status()
    out_path.write_bytes(resp.content)


def tts_save_segment(lang: str, text: str, out_path: Path, attempts: int = 3,
                     use_elevenlabs_for_en: bool = True) -> None:
    """Generate TTS for one segment. lang is 'en' or 'ko'.

    English goes to ElevenLabs first, but only when use_elevenlabs_for_en is
    set and a key is configured; any failure — missing key, exhausted
    credits, 401, network error — falls through to edge-tts so a run never
    dies on the paid path. That fallback is why this channel dropped
    ElevenLabs the first time round (see SETUP.md): a 401 used to abort the
    whole job. Korean always uses edge-tts.

    edge-tts occasionally fails a single call (Microsoft's endpoint is
    unofficial and has no uptime guarantee) even when the vast majority of
    calls in the same run succeed — a real, observed failure mode in a
    ~240-call mega-compilation run. Retrying the one bad call is far cheaper
    than aborting a run that's otherwise almost entirely generated."""
    if lang == "en" and use_elevenlabs_for_en and os.environ.get("ELEVENLABS_API_KEY"):
        try:
            tts_save_elevenlabs(text, out_path)
            return
        except Exception as exc:  # noqa: BLE001 - any failure just falls back
            print(f"ElevenLabs TTS failed, falling back to edge-tts: {exc}", file=sys.stderr)

    voice = EDGE_VOICE_EN if lang == "en" else EDGE_VOICE_KO
    for attempt in range(1, attempts + 1):
        try:
            subprocess.run(
                ["edge-tts", "--voice", voice, "--text", text, "--write-media", str(out_path)],
                check=True,
                capture_output=True,
            )
            return
        except subprocess.CalledProcessError:
            if attempt == attempts:
                raise
            time.sleep(2 * attempt)


def clip_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def generate_silence(duration_seconds: float, out_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", str(duration_seconds),
            "-q:a", "9",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )


def synthesize_narration(segments, out_path: Path, trailing_silence: float = 0.0,
                         use_elevenlabs_for_en: bool = True) -> None:
    """segments: list of (lang, text) where lang is 'en' or 'ko'. Concatenates
    the raw mp3 bytes — edge-tts outputs constant-bitrate mp3, so sequential
    concatenation plays back fine. trailing_silence adds a pause at the end
    (e.g. reading time in a compilation) by appending a generated silent clip."""
    tmp_dir = out_path.parent
    seg_paths = []
    for i, (lang, text) in enumerate(segments):
        seg_path = tmp_dir / f"{out_path.stem}_seg{i}.mp3"
        tts_save_segment(lang, text, seg_path, use_elevenlabs_for_en=use_elevenlabs_for_en)
        seg_paths.append(seg_path)

    if trailing_silence > 0:
        silence_path = tmp_dir / f"{out_path.stem}_silence.mp3"
        generate_silence(trailing_silence, silence_path)
        seg_paths.append(silence_path)

    with open(out_path, "wb") as out_f:
        for seg_path in seg_paths:
            out_f.write(seg_path.read_bytes())
            seg_path.unlink()


def mux_video(image_path: Path, audio_path: Path, out_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image_path),
            "-i", str(audio_path),
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-af", "loudnorm=I=-14:TP=-1.0:LRA=11",
            "-shortest", "-vf", "fps=30",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )


THUMB_WIDTH, THUMB_HEIGHT = 1280, 720


def make_thumbnail(headline: str, sub_phrases, font_path: str, palette) -> Image.Image:
    top_color, bottom_color = palette
    img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), top_color)
    draw = ImageDraw.Draw(img)
    for x in range(THUMB_WIDTH):
        t = x / THUMB_WIDTH
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        draw.line([(x, 0), (x, THUMB_HEIGHT)], fill=(r, g, b))

    # Frosted-glass phrase chips need real alpha blending, which PIL only
    # does on an RGBA layer — drawing RGBA fills directly on an RGB image
    # silently drops the alpha and renders solid, opaque white.
    overlay = Image.new("RGBA", (THUMB_WIDTH, THUMB_HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    headline_font = ImageFont.truetype(font_path, 84)
    phrase_font = ImageFont.truetype(font_path, 46)
    brand_font = ImageFont.truetype(font_path, 30)

    y = draw_centered(draw, headline, headline_font, 90, (255, 255, 255), wrap_width=12, canvas_width=THUMB_WIDTH)
    y += 30

    for phrase in sub_phrases:
        bbox = overlay_draw.textbbox((0, 0), phrase, font=phrase_font)
        box_w = (bbox[2] - bbox[0]) + 60
        box_h = (bbox[3] - bbox[1]) + 30
        bx = (THUMB_WIDTH - box_w) / 2
        overlay_draw.rounded_rectangle(
            [bx, y, bx + box_w, y + box_h], radius=16,
            fill=(255, 255, 255, 60), outline=(200, 230, 225, 200),
        )
        overlay_draw.text((bx + 30, y + 12), phrase, font=phrase_font, fill=(255, 255, 255, 255))
        y += box_h + 18

    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    brand = "매일 영어 한마디 · @200-y3b"
    bbox = draw.textbbox((0, 0), brand, font=brand_font)
    draw.text((THUMB_WIDTH - (bbox[2] - bbox[0]) - 30, THUMB_HEIGHT - 55), brand, font=brand_font, fill=(255, 255, 255))

    return img


def concat_videos(clip_paths, out_path: Path) -> None:
    filelist = out_path.parent / f"{out_path.stem}_filelist.txt"
    filelist.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in clip_paths), encoding="utf-8"
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(filelist),
            "-c", "copy",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    filelist.unlink()
