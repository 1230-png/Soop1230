"""Caption furniture for the food Shorts.

Everything here is a transparent RGBA layer that compose.py burns over
moving footage — subtitle, ingredient callout, step badge, channel mark.
Nothing draws a background: the frame is always real video.

The subtitle follows the convention Korean cooking channels use, bottom
centre in heavy white with a thick dark outline. Stock footage can be any
brightness, so a gradient scrim goes under the text rather than trusting
the clip to be dark enough on its own.
"""

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1920

CHANNEL_NAME = "오늘뭐먹지"
CHANNEL_HANDLE = "@오늘뭐먹지-f2d"

ACCENT = (255, 196, 82)      # golden oil, used for step badges
SUBTITLE_STROKE = (18, 12, 8)

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]


def find_font() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise SystemExit(
        "한글 폰트가 없습니다. 설치: sudo apt-get install -y fonts-noto-cjk"
    )


def _font(size):
    return ImageFont.truetype(find_font(), size)


def subtitle_top(text, size=64, bottom_margin=250, wrap=13):
    """Where the subtitle block starts, so callers can stack above it."""
    lines = textwrap.fill(text, width=wrap).split("\n")
    return HEIGHT - bottom_margin - (size + 18) * len(lines)



def title_overlay(content):
    """Transparent title furniture, to be burned over moving footage."""
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    # Scrims top and bottom: footage is unpredictable, and white type needs a
    # guaranteed dark ground under it however bright the frame gets.
    layer = _scrim_rgba(layer, 0, 520, 150, invert=True)
    layer = _scrim_rgba(layer, HEIGHT - 620, HEIGHT, 190)

    draw = ImageDraw.Draw(layer)
    title_font = _font(96)
    lines = textwrap.fill(content["title"], width=10).split("\n")

    y = HEIGHT - 560
    for line in lines:
        w = draw.textbbox((0, 0), line, font=title_font, stroke_width=10)[2]
        draw.text(((WIDTH - w) / 2, y), line, font=title_font,
                  fill=(255, 255, 255, 255), stroke_width=10,
                  stroke_fill=SUBTITLE_STROKE + (255,))
        y += 120

    hook = content.get("korean", "")
    if hook:
        hook_font = _font(48)
        w = draw.textbbox((0, 0), hook, font=hook_font, stroke_width=7)[2]
        draw.text(((WIDTH - w) / 2, y + 26), hook, font=hook_font,
                  fill=ACCENT + (255,), stroke_width=7,
                  stroke_fill=SUBTITLE_STROKE + (255,))

    return _brand_rgba(layer)


def step_overlay(index, total, text, ingredient=""):
    """Transparent step furniture: subtitle, ingredient chip, badge, brand."""
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    layer = _scrim_rgba(layer, 0, 400, 130, invert=True)

    top = subtitle_top(text)
    layer = _scrim_rgba(layer, max(int(top - 200), 0), HEIGHT, 195)

    draw = ImageDraw.Draw(layer)
    font = _font(64)
    y = top
    for line in textwrap.fill(text, width=13).split("\n"):
        w = draw.textbbox((0, 0), line, font=font, stroke_width=8)[2]
        draw.text(((WIDTH - w) / 2, y), line, font=font,
                  fill=(255, 255, 255, 255), stroke_width=8,
                  stroke_fill=SUBTITLE_STROKE + (255,))
        y += 82

    if ingredient:
        chip_font = _font(52)
        tw = draw.textbbox((0, 0), ingredient, font=chip_font)[2]
        bw, cy = tw + 96, top - 168
        x = (WIDTH - bw) / 2
        draw.rounded_rectangle([x, cy, x + bw, cy + 108], radius=54,
                               fill=(14, 10, 6, 190), outline=ACCENT + (225,), width=3)
        draw.text((x + 48, cy + 24), ingredient, font=chip_font, fill=ACCENT + (255,))

    layer = _badge_rgba(layer, index, total)
    return _brand_rgba(layer)


def _scrim_rgba(layer, y0, y1, opacity, invert=False):
    """Vertical gradient band drawn straight onto an RGBA layer."""
    draw = ImageDraw.Draw(layer)
    span = max(y1 - y0, 1)
    for i in range(span):
        t = i / span
        a = (1 - t) if invert else t
        draw.line([(0, y0 + i), (WIDTH, y0 + i)],
                  fill=(0, 0, 0, int(opacity * (a ** 1.4))))
    return layer


def _badge_rgba(layer, index, total):
    draw = ImageDraw.Draw(layer)
    font = _font(40)
    label = f"STEP {index}"
    tw = draw.textbbox((0, 0), label, font=font)[2]

    x, y = 70, 150
    draw.rounded_rectangle([x, y, x + tw + 60, y + 78], radius=39,
                           fill=(0, 0, 0, 150), outline=ACCENT + (215,), width=3)
    draw.text((x + 30, y + 16), label, font=font, fill=ACCENT + (255,))

    px = x + tw + 96
    for i in range(1, total + 1):
        filled = i <= index
        r = 9 if filled else 7
        cy = y + 39
        draw.ellipse([px - r, cy - r, px + r, cy + r],
                     fill=ACCENT + (255,) if filled else (255, 255, 255, 110))
        px += 34
    return layer


def _brand_rgba(layer):
    draw = ImageDraw.Draw(layer)
    d = 132
    cx, cy = WIDTH - 70 - d, 150
    draw.ellipse([cx, cy, cx + d, cy + d], fill=(24, 16, 10, 210),
                 outline=ACCENT + (235,), width=4)
    for text, font, dy, fill in (
        ("오늘", _font(34), 30, (255, 255, 255, 255)),
        ("뭐먹지", _font(24), 74, ACCENT + (255,)),
    ):
        w = draw.textbbox((0, 0), text, font=font)[2]
        draw.text((cx + (d - w) / 2, cy + dy), text, font=font, fill=fill)

    draw.text((70, HEIGHT - 120), CHANNEL_HANDLE, font=_font(28),
              fill=(255, 255, 255, 165))
    return layer
