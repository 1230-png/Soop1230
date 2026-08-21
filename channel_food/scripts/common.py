"""Shared helpers for the daily Shorts pipeline: font lookup, background
palettes, free neural-voice TTS, ffmpeg muxing/concatenation, ambience
synthesis, and the daily-upload guard.

Voice strategy (100% free, no API key, no payment):
- All narration goes through edge-tts, Microsoft's free neural "Read Aloud"
  voices. The ElevenLabs helpers below are retained for the sibling channel
  that still uses them, but this channel never calls them —
  `tts_save_segment(..., use_elevenlabs_for_en=False)` keeps that path cold.
"""

import asyncio
import csv
import datetime
import os
import subprocess
import sys
import textwrap
import zlib
from pathlib import Path

import edge_tts
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

# "기묘한 현실" 전용 팔레트. 위의 네이비/틸 계열은 밝고 정보성이라
# 기괴한 현상 콘텐츠의 톤과 맞지 않아, 심연 블루/적갈색 계열로 따로 둔다.
WEIRD_PALETTES = [
    ((10, 12, 20), (28, 10, 14)),    # 심연 블랙 -> 마른 핏빛
    ((8, 16, 24), (6, 30, 34)),      # 深海 블루 -> 차가운 청록
    ((20, 10, 24), (34, 16, 10)),    # 자줏빛 어둠 -> 녹슨 적갈
    ((14, 14, 14), (30, 26, 8)),     # 무채색 -> 병든 황토
]

# Natural free neural voices via edge-tts (Microsoft Edge Read Aloud voices,
# no API key, no cost). Deliberately using two distinct voices so the EN/KO
# narration feels like two people, not one robotic reader doing both.
EN_VOICE = "en-US-AvaMultilingualNeural"
KO_VOICE = "ko-KR-SunHiNeural"

# ElevenLabs (optional, free-tier) — a warm, natural male voice well suited
# to calm explainer narration. Override with ELEVENLABS_VOICE_ID if desired.
ELEVENLABS_DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # "Adam", a standard premade voice
ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
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


def pick_palette(seed: str, palettes=None):
    """seed에 대해 항상 같은 팔레트를 돌려준다.

    hash()는 PYTHONHASHSEED로 프로세스마다 랜덤화되므로 실행할 때마다
    색이 바뀐다. crc32는 프로세스와 무관하게 결정적이다.
    """
    table = PALETTES if palettes is None else palettes
    return table[zlib.crc32(seed.encode("utf-8")) % len(table)]


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


async def _tts_save_edge(text: str, voice: str, out_path: Path) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))


def tts_save(text: str, voice: str, out_path: Path) -> None:
    asyncio.run(_tts_save_edge(text, voice, out_path))


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


def tts_save_segment(lang: str, text: str, out_path: Path, use_elevenlabs_for_en: bool = True) -> None:
    """lang is 'en' or 'ko'. English tries ElevenLabs first (only when
    use_elevenlabs_for_en and an API key is configured) and falls back to
    edge-tts on any failure — missing key, exhausted free quota, network
    error, whatever. Korean always uses edge-tts (see module docstring for
    why the free-tier character budget is split this way)."""
    if lang == "en" and use_elevenlabs_for_en and os.environ.get("ELEVENLABS_API_KEY"):
        try:
            tts_save_elevenlabs(text, out_path)
            return
        except Exception as exc:  # noqa: BLE001 - any failure just falls back
            print(f"ElevenLabs TTS failed, falling back to edge-tts: {exc}", file=sys.stderr)

    voice = EN_VOICE if lang == "en" else KO_VOICE
    tts_save(text, voice, out_path)


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


def synthesize_narration(segments, out_path: Path, trailing_silence: float = 0.0, use_elevenlabs_for_en: bool = True) -> None:
    """segments: list of (lang, text) where lang is 'en' or 'ko'. Concatenates
    the raw mp3 bytes — both edge-tts and ElevenLabs output constant-bitrate
    mp3, so sequential concatenation plays back fine (same trick used for the
    previous gTTS pipeline). trailing_silence adds a pause at the end (e.g.
    reading time in a compilation) by appending a generated silent clip.

    주의: 이 바이트 접합 결과는 재생은 되지만 중간에 프레임 헤더가 남아
    ffmpeg 필터에 넣으면 "Header missing"이 뜬다. 필터링할 오디오가
    필요하면 concat_audio()를 쓸 것. (이 채널은 concat_audio만 쓴다.)"""
    tmp_dir = out_path.parent
    seg_paths = []
    for i, (lang, text) in enumerate(segments):
        seg_path = tmp_dir / f"{out_path.stem}_seg{i}.mp3"
        tts_save_segment(lang, text, seg_path, use_elevenlabs_for_en)
        seg_paths.append(seg_path)

    if trailing_silence > 0:
        silence_path = tmp_dir / f"{out_path.stem}_silence.mp3"
        generate_silence(trailing_silence, silence_path)
        seg_paths.append(silence_path)

    with open(out_path, "wb") as out_f:
        for seg_path in seg_paths:
            out_f.write(seg_path.read_bytes())
            seg_path.unlink()


def concat_audio(parts, out_path: Path) -> Path:
    """오디오 파일들을 이어 붙여 하나의 깨끗한 mp3로 만든다.

    원시 mp3 바이트를 그냥 이어 붙이면 중간에 프레임 헤더가 남아
    "Header missing"이 뜨고, 그 깨진 스트림을 libmp3lame으로 다시 인코딩하면
    psymodel assertion으로 ffmpeg가 SIGABRT로 죽는다.
    concat demuxer로 디코딩한 뒤 한 번에 재인코딩해야 안전하다.
    """
    filelist = out_path.parent / f"{out_path.stem}_concat.txt"
    filelist.write_text(
        "".join(f"file '{Path(p).resolve()}'\n" for p in parts), encoding="utf-8"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", str(filelist),
         "-acodec", "libmp3lame", "-q:a", "4", str(out_path)],
        check=True, capture_output=True,
    )
    filelist.unlink(missing_ok=True)
    return out_path


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



# ============================================================================
# 앰비언스 합성 — 샘플 파일 없이 ffmpeg만으로 불길한 배경음을 만든다.
# 외부 API도, 저작권 있는 음원도 쓰지 않으므로 100% 무료다.
# ============================================================================

# anoisesrc의 c= 는 채널 수가 아니라 노이즈 색이다(white/pink/brown/blue/violet).
# 색을 골라 쓰면 EQ를 따로 걸지 않아도 대략의 대역이 잡힌다.
AMBIENCE_LIBRARY = {
    # 낮게 깔리는 지속음. 대부분의 영상에 바탕으로 깔린다.
    "low_drone": [
        "-f", "lavfi", "-i", "sine=f=45:d={d}",
        "-f", "lavfi", "-i", "anoisesrc=a=0.25:r=44100:c=brown:d={d}",
        "-filter_complex",
        "[0]volume=0.5[s];[1]lowpass=f=200,volume=0.6[n];[s][n]amix=inputs=2:duration=shortest",
    ],
    # 72bpm 정도로 맥동하는 저음. 긴장감을 만든다.
    "heartbeat": [
        "-f", "lavfi", "-i", "sine=f=60:d={d}",
        "-af", "apulsator=hz=1.2:amount=1,volume=0.6",
    ],
    # 바람이 새는 듯한 중저역 노이즈.
    "wind_howl": [
        "-f", "lavfi", "-i", "anoisesrc=a=0.4:r=44100:c=pink:d={d}",
        "-af", "bandpass=f=140:width_type=o:w=2,volume=0.7",
    ],
    # 아주 옅은 고역 잡음. 오래된 녹음 같은 질감을 준다.
    "static_hiss": [
        "-f", "lavfi", "-i", "anoisesrc=a=0.15:r=44100:c=white:d={d}",
        "-af", "highpass=f=3000,volume=0.4",
    ],
}

# 나레이션 대비 배경음 비율. 말소리를 덮지 않도록 낮게 잡는다.
AMBIENCE_GAIN = 0.18


def probe_duration(path: Path) -> float:
    """ffprobe로 오디오/비디오 길이를 초 단위로 잰다. 실패하면 0.0."""
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True, capture_output=True, text=True,
        )
        return float(out.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


def generate_ambience(kind: str, duration_sec: float, out_path: Path) -> Path:
    """앰비언스 한 종류를 duration_sec 길이로 합성한다."""
    if kind not in AMBIENCE_LIBRARY:
        raise KeyError(f"unknown ambience: {kind}")
    d = f"{duration_sec:.2f}"
    args = [a.replace("{d}", d) for a in AMBIENCE_LIBRARY[kind]]
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args,
         "-t", d, "-q:a", "5", "-acodec", "libmp3lame", str(out_path)],
        check=True, capture_output=True,
    )
    return out_path


def mix_ambience(kinds, duration_sec: float, out_path: Path):
    """여러 앰비언스를 겹쳐 한 트랙으로 만든다.

    알 수 없는 종류는 건너뛰고, 하나도 못 만들면 None을 돌려준다
    (호출부는 배경음 없이 나레이션만으로 진행한다).
    """
    tmp_dir = out_path.parent
    made = []
    for i, kind in enumerate(kinds):
        if kind not in AMBIENCE_LIBRARY:
            print(f"  [건너뜀] 알 수 없는 앰비언스: {kind}", file=sys.stderr)
            continue
        part = tmp_dir / f"{out_path.stem}_amb{i}.mp3"
        try:
            made.append(generate_ambience(kind, duration_sec, part))
        except subprocess.CalledProcessError as exc:
            print(f"  [건너뜀] 앰비언스 생성 실패 {kind}: {exc}", file=sys.stderr)

    if not made:
        return None

    if len(made) == 1:
        made[0].replace(out_path)
    else:
        inputs = []
        for part in made:
            inputs += ["-i", str(part)]
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
             "-filter_complex", f"amix=inputs={len(made)}:duration=longest:normalize=0",
             "-q:a", "5", "-acodec", "libmp3lame", str(out_path)],
            check=True, capture_output=True,
        )
        for part in made:
            part.unlink(missing_ok=True)

    return out_path


def mix_narration_with_ambience(narration_path: Path, ambience_path: Path, out_path: Path) -> Path:
    """나레이션 위에 배경음을 낮게 깔아 하나의 트랙으로 만든다.

    길이는 나레이션에 맞춘다(first). 배경음이 짧으면 apad로 늘린다.
    """
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(narration_path),
            "-i", str(ambience_path),
            "-filter_complex",
            f"[1]volume={AMBIENCE_GAIN},apad[bg];"
            f"[0][bg]amix=inputs=2:duration=first:normalize=0,"
            f"loudnorm=I=-14:TP=-1.0:LRA=11",
            "-q:a", "4", "-acodec", "libmp3lame",
            str(out_path),
        ],
        check=True, capture_output=True,
    )
    return out_path


# ============================================================================
# 업로드 한도 방어
# ============================================================================

# YouTube videos.insert는 1회 1,600 units, 일일 기본 할당량은 10,000이다.
# 하루 1편이면 1,600 units만 쓰므로 재시도 여유까지 충분히 남는다.
MAX_DAILY_UPLOADS = 1


def count_today_uploads(log_path: Path) -> int:
    """used_log.csv에서 오늘 날짜로 기록된 행 수를 센다.

    date 컬럼은 datetime.now().isoformat()으로 저장된 naive 로컬 시각이라
    (예: 2026-08-21T10:58:17.246736) 오늘 날짜 접두사로 비교한다.
    """
    if not log_path.exists():
        return 0

    today = datetime.date.today().isoformat()
    count = 0
    try:
        with open(log_path, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if (row.get("date") or "").startswith(today):
                    count += 1
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        # 로그를 못 읽으면 "0건"으로 넘기지 않는다. 그랬다가는 손상된 로그가
        # 곧바로 무제한 업로드로 이어진다. 한도에 도달한 것으로 간주해 막는다.
        print(f"[경고] 업로드 로그를 읽을 수 없어 안전하게 차단합니다: {exc}", file=sys.stderr)
        return MAX_DAILY_UPLOADS

    return count


def daily_quota_exhausted(log_path: Path) -> bool:
    return count_today_uploads(log_path) >= MAX_DAILY_UPLOADS
