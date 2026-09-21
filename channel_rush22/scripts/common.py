"""Shared rendering / narration / muxing helpers for the @Rush22 shorts.

Everything here is free and key-less on purpose:
- Pillow          : background + text cards
- edge-tts        : Microsoft neural voices (no API key, no monthly quota)
- ffmpeg          : per-scene muxing and final concatenation

The @200-y3b channel in this repo renders one static card per video. This
channel renders one card *per scene* and concatenates them, because a Short
that never changes on screen loses viewers within the first few seconds and
retention is what the Shorts feed actually ranks on.
"""

import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1920

# Safe area: YouTube's Shorts UI covers roughly the bottom 380px (title,
# channel handle, action rail) and the top ~180px. Text drawn outside these
# bounds gets covered by the player chrome on a real phone.
MARGIN_X = 90
SAFE_TOP = 300
SAFE_BOTTOM = HEIGHT - 480

# High-energy palettes for a "rush" feel. Each scene kind gets its own so the
# video visibly changes as it plays.
PALETTES = {
    "hook": ((14, 16, 34), (86, 18, 46)),      # near-black -> crimson
    "body": ((12, 22, 38), (10, 44, 60)),      # navy -> deep teal
    "punch": ((24, 14, 38), (78, 42, 10)),     # plum -> amber
}

ACCENT = {
    "hook": (255, 92, 92),
    "body": (94, 214, 200),
    "punch": (255, 186, 74),
}

BRAND = "머니러시"

# edge-tts Korean neural voices. InJoon reads as calm/credible, which suits
# money content better than the brighter SunHi.
VOICE_KO = os.environ.get("RUSH_VOICE", "ko-KR-InJoonNeural")
# Slightly quicker than default — matches the channel name and the pacing
# that Shorts rewards, without tipping into the sped-up TTS sound.
VOICE_RATE = os.environ.get("RUSH_VOICE_RATE", "+12%")

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
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
        "then re-run."
    )


# --------------------------------------------------------------------------
# Background
# --------------------------------------------------------------------------

def make_background(kind: str) -> Image.Image:
    """Vertical gradient plus faint diagonal speed streaks."""
    top_color, bottom_color = PALETTES[kind]
    img = Image.new("RGB", (WIDTH, HEIGHT), top_color)
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / HEIGHT
        draw.line(
            [(0, y), (WIDTH, y)],
            fill=tuple(
                int(top_color[i] + (bottom_color[i] - top_color[i]) * t)
                for i in range(3)
            ),
        )

    streaks = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    streak_draw = ImageDraw.Draw(streaks)
    r, g, b = ACCENT[kind]
    for i in range(-4, 14):
        x = i * 190
        streak_draw.polygon(
            [(x, 0), (x + 26, 0), (x + 26 - 520, HEIGHT), (x - 520, HEIGHT)],
            fill=(r, g, b, 12),
        )
    return Image.alpha_composite(img.convert("RGBA"), streaks).convert("RGB")


# --------------------------------------------------------------------------
# Text layout
# --------------------------------------------------------------------------

def wrap_to_width(draw, text: str, font, max_px: int):
    """Wrap by measured pixel width rather than character count.

    Character-count wrapping (textwrap.fill) misbehaves on mixed Korean/latin
    text because a Hangul syllable is roughly twice as wide as an ascii
    character, so a width tuned for one is wrong for the other. Long unbroken
    Korean runs have no spaces to break on, so those fall back to per-character
    accumulation.
    """
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        line = ""
        for token in _tokenize(paragraph):
            candidate = line + token
            if line and draw.textlength(candidate.strip(), font=font) > max_px:
                lines.append(line.strip())
                line = token.lstrip()
            else:
                line = candidate
        if line.strip():
            lines.append(line.strip())
    return lines


def _tokenize(paragraph: str):
    """Split into space-delimited words, but break bare Korean runs longer than
    a few syllables into single characters so they can wrap at all."""
    for word in paragraph.split(" "):
        if len(word) > 8 and " " not in word and not word.isascii():
            for ch in word:
                yield ch
            yield " "
        else:
            yield word + " "


def line_height(draw, font) -> int:
    # Use fixed reference glyphs so the height does not jitter between lines
    # that happen to contain no descenders.
    bbox = draw.textbbox((0, 0), "가Ay", font=font)
    return bbox[3] - bbox[1]


def draw_block(draw, text, font, top_y, fill, line_gap=22, shadow=True) -> int:
    """Draw a centered, wrapped block starting at top_y. Returns the y after it."""
    max_px = WIDTH - 2 * MARGIN_X
    lines = wrap_to_width(draw, text, font, max_px)
    lh = line_height(draw, font)
    y = top_y
    for line in lines:
        if not line:
            y += lh + line_gap
            continue
        w = draw.textlength(line, font=font)
        x = (WIDTH - w) / 2
        if shadow:
            draw.text((x + 3, y + 4), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=fill)
        y += lh + line_gap
    return y


def measure_block(draw, text, font, line_gap=22) -> int:
    lines = wrap_to_width(draw, text, font, WIDTH - 2 * MARGIN_X)
    return len(lines) * (line_height(draw, font) + line_gap) - line_gap


def draw_badge(draw, text, font, y, accent) -> int:
    """Small pill-shaped label, centered."""
    tw = draw.textlength(text, font=font)
    th = line_height(draw, font)
    pad_x, pad_y = 34, 18
    box_w = tw + pad_x * 2
    x = (WIDTH - box_w) / 2
    draw.rounded_rectangle(
        [x, y, x + box_w, y + th + pad_y * 2], radius=(th + pad_y * 2) / 2,
        fill=accent,
    )
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=(16, 16, 20))
    return y + th + pad_y * 2


def draw_brand(draw, font, kind) -> None:
    """Channel watermark, kept just below the content area and above the band
    the Shorts player covers with the title and channel handle."""
    label = f"{BRAND} · @Rush22"
    w = draw.textlength(label, font=font)
    draw.text(((WIDTH - w) / 2, SAFE_BOTTOM + 20), label, font=font, fill=ACCENT[kind])


# --------------------------------------------------------------------------
# Narration
# --------------------------------------------------------------------------

def tts_save(text: str, out_path: Path) -> None:
    subprocess.run(
        [
            "edge-tts",
            "--voice", VOICE_KO,
            "--rate", VOICE_RATE,
            "--text", text,
            "--write-media", str(out_path),
        ],
        check=True,
        capture_output=True,
    )


def generate_silence(seconds: float, out_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", str(seconds), "-q:a", "9",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )


def narrate(text: str, out_path: Path, trailing_silence: float = 0.35) -> None:
    """One scene's narration, with a short pause appended so scenes do not
    run into each other. edge-tts emits constant-bitrate mp3, so raw byte
    concatenation plays back correctly."""
    tmp = out_path.parent
    speech = tmp / f"{out_path.stem}_speech.mp3"
    tts_save(text, speech)

    parts = [speech]
    if trailing_silence > 0:
        pause = tmp / f"{out_path.stem}_pause.mp3"
        generate_silence(trailing_silence, pause)
        parts.append(pause)

    with open(out_path, "wb") as f:
        for part in parts:
            f.write(part.read_bytes())
            part.unlink()


# --------------------------------------------------------------------------
# Video
# --------------------------------------------------------------------------

def mux_scene(image_path: Path, audio_path: Path, out_path: Path) -> None:
    """One still image + one narration track -> one mp4 scene.

    Every scene is encoded with identical parameters so the final concat can
    use stream copy instead of a re-encode.
    """
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image_path),
            "-i", str(audio_path),
            "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage",
            "-pix_fmt", "yuv420p", "-r", "30", "-g", "60",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-af", "loudnorm=I=-14:TP=-1.0:LRA=11",
            "-shortest",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )


def concat_scenes(clip_paths, out_path: Path) -> None:
    filelist = out_path.parent / f"{out_path.stem}_files.txt"
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


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())
