"""장면을 화면으로 그리고 ffmpeg 로 영상을 조립한다.

수치를 다루는 채널이라 화면은 건조하게 간다. 배경은 단색 그라데이션,
가운데에 화면 문구 하나. 자극적인 연출을 넣지 않는 것이 채널 원칙이다.
"""

import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1920, 1080
THUMB_WIDTH, THUMB_HEIGHT = 1280, 720
BG_TOP = (14, 20, 32)
BG_BOTTOM = (10, 32, 42)
FG = (238, 242, 246)
MUTED = (140, 158, 176)

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
]


def find_korean_font():
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise SystemExit(
        "한글 폰트를 찾지 못했다. 설치할 것:\n"
        "  Ubuntu: sudo apt-get install -y fonts-noto-cjk\n"
        "  Windows: 맑은 고딕이 기본 설치돼 있다. 경로를 확인할 것."
    )


def _font(size):
    return ImageFont.truetype(find_korean_font(), size)


def _gradient(width, height, top=BG_TOP, bottom=BG_BOTTOM):
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        draw.line(
            [(0, y), (width, y)],
            fill=tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)),
        )
    return image


def _draw_block(draw, text, font, top, width, color, wrap, gap):
    """가운데 정렬로 여러 줄을 그리고 마지막 y 를 돌려준다."""
    y = top
    for line in textwrap.fill(text, width=wrap).split("\n"):
        box = draw.textbbox((0, 0), line, font=font)
        draw.text(((width - (box[2] - box[0])) / 2, y), line, font=font, fill=color)
        y += (box[3] - box[1]) + gap
    return y


def slide(screen_text, section, out_path, source_note=None):
    """장면 한 컷. 화면 문구가 주인공이고 섹션 이름은 작게 남긴다."""
    image = _gradient(WIDTH, HEIGHT)
    draw = ImageDraw.Draw(image)

    _draw_block(draw, section, _font(40), 120, WIDTH, MUTED, 40, 12)
    body = _font(84)
    lines = len(textwrap.fill(screen_text, width=18).split("\n"))
    _draw_block(draw, screen_text, body, HEIGHT / 2 - lines * 60, WIDTH, FG, 18, 28)

    if source_note:
        note = _font(32)
        box = draw.textbbox((0, 0), source_note, font=note)
        draw.text(
            ((WIDTH - (box[2] - box[0])) / 2, HEIGHT - 110), source_note, font=note, fill=MUTED
        )
    image.save(out_path)
    return out_path


def thumbnail(title, out_path, subtitle=None):
    image = _gradient(THUMB_WIDTH, THUMB_HEIGHT)
    draw = ImageDraw.Draw(image)
    lines = len(textwrap.fill(title, width=14).split("\n"))
    end = _draw_block(
        draw, title, _font(84), THUMB_HEIGHT / 2 - lines * 58, THUMB_WIDTH, FG, 14, 22
    )
    if subtitle:
        _draw_block(draw, subtitle, _font(38), end + 24, THUMB_WIDTH, MUTED, 30, 10)
    image.save(out_path)
    return out_path


def audio_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def mux(image_path, audio_path, out_path):
    """정지 화면 + 음성 → 영상 한 토막."""
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-loop", "1", "-i", str(image_path),
         "-i", str(audio_path),
         "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
         "-r", "30", "-c:a", "aac", "-b:a", "192k",
         "-shortest", str(out_path)],
        check=True, capture_output=True,
    )
    return out_path


def concat(parts, out_path, workdir):
    """토막들을 하나로 잇는다."""
    listing = Path(workdir) / "parts.txt"
    listing.write_text(
        "".join(f"file '{Path(p).resolve().as_posix()}'\n" for p in parts), encoding="utf-8"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", str(out_path)],
        check=True, capture_output=True,
    )
    listing.unlink(missing_ok=True)
    return out_path
