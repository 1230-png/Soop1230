"""Shared helpers for both the daily Shorts and the weekly long-form
compilation: font lookup, background palettes, natural neural-voice TTS,
and ffmpeg muxing/concatenation.

Voice strategy (all free tiers, no payment):
- English narration on the daily Shorts uses ElevenLabs (by far the most
  natural-sounding free option) IF an ELEVENLABS_API_KEY secret is set —
  its free plan is only 10,000 characters/month, which comfortably covers
  the Shorts' English lines (~7,000 chars/month) but not the long-form
  compilations too, so those stay on edge-tts to not blow the quota.
- Everything else (Korean narration always, English whenever ElevenLabs
  isn't configured or its call fails/quota runs out) falls back to
  edge-tts — Microsoft's free neural "Read Aloud" voices, no API key,
  still far more natural than gTTS.
"""

import asyncio
import os
import subprocess
import sys
import textwrap
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
    reading time in a compilation) by appending a generated silent clip."""
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
# 🎵 Food Sound Effects System - ASMR 오디오 효과음 추가
# ============================================================================

FOOD_SOUND_LIBRARY = {
    # Cooking sounds
    "water_boiling": {"duration": 3.0, "volume": 0.4},
    "soup_bubbling": {"duration": 2.5, "volume": 0.35},
    "stew_simmering": {"duration": 4.0, "volume": 0.3},
    "noodles_cooking": {"duration": 2.0, "volume": 0.35},
    "noodles_stirring": {"duration": 2.5, "volume": 0.4},
    "pasta_cooking": {"duration": 3.0, "volume": 0.35},

    # Frying sounds
    "sizzle_fry": {"duration": 3.0, "volume": 0.6},
    "hot_oil_sizzle": {"duration": 3.5, "volume": 0.65},
    "frying_crackling": {"duration": 4.0, "volume": 0.6},
    "butter_sizzling": {"duration": 2.5, "volume": 0.5},
    "dumpling_splashing": {"duration": 2.0, "volume": 0.45},

    # Preparation sounds
    "cutting_knife": {"duration": 2.0, "volume": 0.4},
    "egg_beating": {"duration": 2.5, "volume": 0.45},
    "egg_frying": {"duration": 1.5, "volume": 0.35},
    "egg_dropping": {"duration": 0.8, "volume": 0.3},

    # ASMR-style eating sounds
    "chewing": {"duration": 2.0, "volume": 0.35},
    "slurping": {"duration": 1.5, "volume": 0.4},
    "crunching_coating": {"duration": 1.5, "volume": 0.45},
    "sipping": {"duration": 1.2, "volume": 0.3},

    # Ambient/machine sounds
    "air_fryer_fan": {"duration": 3.0, "volume": 0.25},
    "timer_beeping": {"duration": 0.5, "volume": 0.4},
    "pan_clattering": {"duration": 1.0, "volume": 0.35},
    "unwrapping_packaging": {"duration": 1.5, "volume": 0.3},
    "sauce_pouring": {"duration": 1.5, "volume": 0.4},
}


def generate_food_sound_effect(sound_type: str, duration_sec: float, out_path: Path) -> Path:
    """
    음식 소리 효과를 ffmpeg 신테사이저로 생성합니다.
    (프로토타입: 톤 기반 ASMR 배경음 생성)
    """
    sound_config = FOOD_SOUND_LIBRARY.get(sound_type, {"duration": 2.0, "volume": 0.4})

    # 각 음식 소리 유형별 톤 주파수 할당 (ASMR 느낌)
    frequencies = {
        # 저음 (65-125 Hz) - 물 끓는 소리, 냄비 소리
        "water_boiling": 85,
        "soup_bubbling": 75,
        "stew_simmering": 70,
        "pan_clattering": 120,

        # 중저음 (125-250 Hz) - 면 요리, 프라이
        "noodles_cooking": 160,
        "noodles_stirring": 150,
        "pasta_cooking": 140,
        "sizzle_fry": 200,
        "hot_oil_sizzle": 180,

        # 중음 (250-500 Hz) - 계란, 튀김
        "egg_beating": 320,
        "egg_frying": 300,
        "frying_crackling": 280,
        "butter_sizzling": 250,
        "crunching_coating": 400,

        # 중고음 (500-2000 Hz) - 식음 소리
        "chewing": 600,
        "slurping": 800,
        "sipping": 700,

        # 고음 (2000+ Hz) - 칼, 타이머
        "cutting_knife": 2500,
        "timer_beeping": 3000,
        "egg_dropping": 1500,
        "unwrapping_packaging": 1200,

        # 기계음
        "air_fryer_fan": 180,
        "sauce_pouring": 400,
        "dumpling_splashing": 250,
    }

    freq = frequencies.get(sound_type, 250)
    volume = min(sound_config["volume"], 1.0)
    actual_duration = min(duration_sec, sound_config["duration"])

    # ffmpeg 신테사이저로 톤 생성 (ASMR 느낌)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anoisesrc=a={volume}:r=44100:c=1",
            "-f", "lavfi", "-i", f"sine=f={freq}:d={actual_duration}",
            "-filter_complex", f"[1]volume={volume*0.7}[sine]; [0][sine]amix=inputs=2:duration=longest",
            "-t", str(actual_duration),
            "-q:a", "5",
            "-acodec", "libmp3lame",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )

    return out_path


def mix_food_sounds_asmr(sound_effects_list, duration_sec: float, output_dir: Path, content_id: int) -> Path:
    """
    음식 소리 효과들을 ASMR 스타일로 혼합합니다.

    Args:
        sound_effects_list: 사운드 효과 이름 리스트 (예: ["water_boiling", "sizzle_fry"])
        duration_sec: 목표 비디오 길이 (초)
        output_dir: 출력 디렉토리
        content_id: 콘텐츠 ID

    Returns:
        혼합된 오디오 파일 경로
    """
    if not sound_effects_list:
        # 기본 ASMR 배경음: 미묘한 주방 소음
        sound_effects_list = ["soup_bubbling", "air_fryer_fan"]

    # 각 사운드 효과 파일 생성
    sound_files = []
    for effect in sound_effects_list:
        if effect in FOOD_SOUND_LIBRARY:
            effect_path = output_dir / f"sfx_{content_id}_{effect}.mp3"
            try:
                generate_food_sound_effect(effect, duration_sec, effect_path)
                sound_files.append(effect_path)
            except Exception as e:
                print(f"  ⚠️  음식 소리 생성 실패 ({effect}): {str(e)[:60]}", file=sys.stderr)

    # 다중 효과음 혼합
    output_path = output_dir / f"food_sounds_{content_id}.mp3"

    if len(sound_files) == 0:
        print(f"  ⚠️  음식 소리 효과 생성 건너뜀: 사용 가능한 사운드 없음", file=sys.stderr)
        # 침묵 생성
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
                "-t", str(duration_sec),
                "-q:a", "5",
                "-acodec", "libmp3lame",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )
        return output_path

    if len(sound_files) == 1:
        # 단일 파일: 복사만
        subprocess.run(["cp", str(sound_files[0]), str(output_path)], check=True)
    else:
        # 다중 파일: ffmpeg amix로 혼합
        input_args = []
        for i, f in enumerate(sound_files):
            input_args.extend(["-i", str(f)])

        # amix 필터: 모든 입력을 혼합
        amix_filter = f"[0]" + "".join(f"[{i}]" for i in range(1, len(sound_files))) + \
                     f"amix=inputs={len(sound_files)}:duration=longest"

        subprocess.run(
            [
                "ffmpeg", "-y",
                *input_args,
                "-filter_complex", amix_filter,
                "-t", str(duration_sec),
                "-q:a", "5",
                "-acodec", "libmp3lame",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )

    # 임시 파일 정리
    for f in sound_files:
        f.unlink(missing_ok=True)

    return output_path
