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


# ─── 캔들차트 화면 ────────────────────────────────────────────────────
#
# 참고 영상들은 차트가 배경이 아니라 화면 그 자체다. 축도 눈금도 거의 없고
# 검은 바탕에 캔들만 꽉 찬다. 그 위에 말하는 문장이 자막으로 붙는다.
# PIL 로 직접 그린다 — 축·범례를 붙이지 않을 거라 차트 라이브러리가 필요 없고,
# 색과 두께를 화면에 맞춰 그대로 정할 수 있다.

CHART_BG = (8, 10, 14)
UP_COLOR = (38, 166, 154)
DOWN_COLOR = (239, 83, 80)
GRID = (26, 30, 38)
HIGHLIGHT = (235, 64, 52)
SUBTITLE_FG = (255, 255, 255)
# 박스를 깔지 않고 검은 외곽선만 두른다. 차트가 가려지지 않으면서 글자는 읽힌다.
SUBTITLE_STROKE = (0, 0, 0)
STROKE_WIDTH = 7
# 화면보다 넓게 그려 두고 ffmpeg 가 그 위를 훑는다. 매 프레임을 PIL 로 그리면
# 몇 시간이 걸리는데, 이렇게 하면 한 장만 그리고도 30fps 로 흐른다.
PAN_WIDTH = WIDTH * 2


def _price_bounds(ohlc):
    low = float(ohlc["Low"].min())
    high = float(ohlc["High"].max())
    if high <= low:
        high = low + 1.0
    pad = (high - low) * 0.08
    return low - pad, high + pad


def candle_chart(ohlc, out_path, highlight=None, width=WIDTH, height=HEIGHT,
                 top_margin=90, bottom_margin=260):
    """검은 바탕에 캔들만 그린다.

    highlight 는 (시작 인덱스, 끝 인덱스). 참고 영상이 빨간 사각형으로 볼 곳을
    짚는 것과 같은 역할이다. 어디를 보라고 화면이 직접 가리켜야 한다.

    아래쪽을 비워 두는 이유는 자막이 그 자리에 앉기 때문이다.
    """
    image = Image.new("RGB", (width, height), CHART_BG)
    draw = ImageDraw.Draw(image)
    count = len(ohlc)
    if count == 0:
        image.save(out_path)
        return out_path

    low, high = _price_bounds(ohlc)
    plot_height = height - top_margin - bottom_margin
    span = high - low

    def y_of(price):
        return top_margin + (high - float(price)) / span * plot_height

    for fraction in (0.25, 0.5, 0.75):
        y = top_margin + plot_height * fraction
        draw.line([(0, y), (width, y)], fill=GRID, width=1)

    slot = width / count
    body = max(1, int(slot * 0.62))
    wick = max(1, body // 5)

    opens = ohlc["Open"].to_numpy()
    highs = ohlc["High"].to_numpy()
    lows = ohlc["Low"].to_numpy()
    closes = ohlc["Close"].to_numpy()

    for index in range(count):
        center = slot * (index + 0.5)
        color = UP_COLOR if closes[index] >= opens[index] else DOWN_COLOR
        draw.line(
            [(center, y_of(highs[index])), (center, y_of(lows[index]))],
            fill=color, width=wick,
        )
        top = y_of(max(opens[index], closes[index]))
        bottom = y_of(min(opens[index], closes[index]))
        if bottom - top < 1:
            bottom = top + 1
        draw.rectangle(
            [center - body / 2, top, center + body / 2, bottom], fill=color
        )

    if highlight:
        start, end = highlight
        left = max(0, slot * start)
        right = min(width, slot * (end + 1))
        draw.rectangle(
            [left, top_margin, right, top_margin + plot_height],
            outline=HIGHLIGHT, width=4,
        )

    image.save(out_path)
    return out_path


def _write_stroked(draw, xy, text, font, fill=SUBTITLE_FG):
    draw.text(
        xy, text, font=font, fill=fill,
        stroke_width=STROKE_WIDTH, stroke_fill=SUBTITLE_STROKE,
    )


def _subtitle_lines(draw, text, font, wrap, width, height, bottom):
    lines = textwrap.fill(text, width=wrap).split("\n")
    line_height = font.size + 18
    y = height - bottom - line_height * len(lines)
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        yield line, (width - (box[2] - box[0])) / 2, y
        y += line_height


def subtitle_overlay(text, out_path, label=None, width=WIDTH, height=HEIGHT,
                     size=58, wrap=26, bottom=150):
    """자막만 담은 투명 PNG.

    배경이 흐르는 동안 자막은 제자리에 있어야 해서, 차트에 굽지 않고
    따로 만들어 ffmpeg 가 위에 얹는다.
    """
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _font(size)
    for line, x, y in _subtitle_lines(draw, text, font, wrap, width, height, bottom):
        _write_stroked(draw, (x, y), line, font)
    if label:
        small = _font(38)
        _write_stroked(draw, (64, 44), label, small, fill=MUTED)
    image.save(out_path)
    return out_path


def draw_subtitle(image_path, text, out_path=None, width=WIDTH, height=HEIGHT,
                  size=58, wrap=26, bottom=150):
    """정지 화면에 자막을 직접 굽는다. 미리보기용."""
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = _font(size)
    for line, x, y in _subtitle_lines(draw, text, font, wrap, width, height, bottom):
        _write_stroked(draw, (x, y), line, font)
    image.save(out_path or image_path)
    return out_path or image_path


def caption_strip(image_path, label, out_path=None, size=38, top=44, left=64):
    """왼쪽 위에 무엇을 보고 있는지 한 줄. 차트만 있으면 맥락이 없다."""
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    _write_stroked(draw, (left, top), label, _font(size), fill=MUTED)
    image.save(out_path or image_path)
    return out_path or image_path


def pan_mux(wide_image, overlay_png, audio_path, out_path, seconds,
            width=WIDTH, height=HEIGHT):
    """넓은 차트 위를 훑으며 자막을 얹어 한 토막을 만든다.

    crop 창을 시간에 따라 옮긴다. 배경은 흐르고 자막은 고정된다.
    """
    travel = max(seconds, 0.1)
    chain = (
        f"[0:v]crop={width}:{height}:"
        f"x='(iw-{width})*min(t/{travel:.3f}\,1)':y=0,fps=30[bg];"
        "[bg][1:v]overlay=0:0[v]"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-loop", "1", "-i", str(wide_image),
         "-loop", "1", "-i", str(overlay_png),
         "-i", str(audio_path),
         "-filter_complex", chain,
         "-map", "[v]", "-map", "2:a",
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k",
         "-shortest", str(out_path)],
        check=True, capture_output=True,
    )
    return out_path
