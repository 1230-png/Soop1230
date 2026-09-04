"""머니로직 영상 UI 생성 (Pillow).

타이틀, 자막, 차트 레이블, 워터마크, 아웃트로, 진행바를 PNG로 생성한다.
moviepy는 사용하지 않고 Pillow로만 작업해서 ImageMagick 의존을 피한다.
"""

import platform
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1920, 1080

# 색상 팔레트 (다크테마)
BG_DARK = (15, 23, 42)      # #0F172A
TEXT_WHITE = (255, 255, 255)
ACCENT_BLUE = (56, 189, 248) # #38BDF8 (sky-500)
ACCENT_YELLOW = (234, 179, 8) # #EAB308 (yellow-500)
SUBTLE_GRAY = (71, 85, 105)   # #475569 (slate-600)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """한글 지원 폰트를 로드한다. Windows/Linux 크로스 플랫폼."""
    candidates = []
    system = platform.system()

    if system == "Windows":
        candidates = [
            "C:\\Windows\\Fonts\\malgunbd.ttf",  # 맑은 고딕 볼드
            "C:\\Windows\\Fonts\\malgun.ttf",    # 맑은 고딕
            "C:\\Windows\\Fonts\\arial.ttf",
        ]
    else:  # Linux, macOS
        candidates = [
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]

    for path_str in candidates:
        try:
            return ImageFont.truetype(path_str, size=size)
        except (OSError, IOError):
            continue

    # 폰트를 찾을 수 없으면 기본 폰트 사용 (제한적이지만 동작)
    return ImageFont.load_default()


def line_height(font: ImageFont.FreeTypeFont) -> int:
    """폰트의 행 높이 (ascent + descent)를 반환한다.

    bounding box 높이가 아니라 실제 행 간격을 구한다.
    이 값을 사용하면 텍스트 겹침을 피할 수 있다.
    """
    metrics = font.getmetrics()
    return metrics[0] + metrics[1]  # ascent + descent


def make_background() -> Image.Image:
    """1920×2150 그라데이션 배경을 만든다.

    프레임(1920×1080)보다 크므로 panning 시 빈 공간이 생기지 않는다.
    느린 sine-wave 이동(panning)으로 배경이 흐른다.
    """
    bg = Image.new("RGB", (1920, 2150), BG_DARK)
    draw = ImageDraw.Draw(bg, "RGBA")

    # 그라데이션: 위에서 아래로 어두운 -> 약간 밝은 -> 어두운
    for y in range(2150):
        # sine 곡선으로 부드러운 명암 변화
        import math
        factor = 0.5 + 0.3 * math.sin(math.pi * y / 2150)
        r = int(15 * factor)
        g = int(23 * factor)
        b = int(42 * factor)
        draw.line([(0, y), (1920, y)], fill=(r, g, b))

    # 격자 패턴 (미묘하게)
    grid_spacing = 120
    for x in range(0, 1920, grid_spacing):
        draw.line([(x, 0), (x, 2150)], fill=(51, 65, 85, 30))
    for y in range(0, 2150, grid_spacing):
        draw.line([(0, y), (1920, y)], fill=(51, 65, 85, 30))

    # Vignette 효과 (모서리 어둡게)
    overlay = Image.new("RGBA", (1920, 2150), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for i in range(200):
        alpha = int(80 * (i / 200))
        overlay_draw.ellipse(
            [(-400 + i, -400 + i), (2320 - i, 2550 - i)],
            fill=(0, 0, 0, alpha),
        )
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")

    return bg


def make_title_card(ticker: str, topic: str, date_str: str) -> Image.Image:
    """타이틀 카드를 만든다. RGBA 반환."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 배경: 반투명 다크 오버레이
    draw.rectangle(
        [(0, 0), (WIDTH, HEIGHT)],
        fill=(*BG_DARK, 200),
    )

    # 틱커 (큼)
    ticker_font = load_font(120, bold=True)
    ticker_bbox = draw.textbbox((0, 0), ticker, font=ticker_font)
    ticker_w = ticker_bbox[2] - ticker_bbox[0]
    ticker_x = (WIDTH - ticker_w) // 2
    draw.text(
        (ticker_x, 250),
        ticker,
        fill=ACCENT_BLUE,
        font=ticker_font,
    )

    # 주제 (중간)
    topic_font = load_font(48)
    topic_bbox = draw.textbbox((0, 0), topic, font=topic_font)
    topic_w = topic_bbox[2] - topic_bbox[0]
    topic_x = (WIDTH - topic_w) // 2
    draw.text(
        (topic_x, 430),
        topic,
        fill=TEXT_WHITE,
        font=topic_font,
    )

    # 날짜 (작음)
    date_font = load_font(32)
    date_bbox = draw.textbbox((0, 0), date_str, font=date_font)
    date_w = date_bbox[2] - date_bbox[0]
    date_x = (WIDTH - date_w) // 2
    draw.text(
        (date_x, 550),
        date_str,
        fill=SUBTLE_GRAY,
        font=date_font,
    )

    # 밑줄 (파란색 액센트)
    underline_y = 620
    draw.rectangle(
        [(400, underline_y), (1520, underline_y + 3)],
        fill=ACCENT_BLUE,
    )

    return img


def make_subtitle(text: str) -> Image.Image:
    """자막을 만든다. RGBA 반환. 하단에 놓인다."""
    img = Image.new("RGBA", (WIDTH, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 반투명 배경
    draw.rectangle(
        [(50, 30), (WIDTH - 50, 170)],
        fill=(15, 23, 42, 220),
        outline=(56, 189, 248, 100),
        width=2,
    )

    # 텍스트 (한 줄 또는 여러 줄)
    font = load_font(28)
    line_h = line_height(font)

    # 단어 래핑
    words = text.split()
    lines = []
    current_line = []
    max_width = WIDTH - 120

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_w = bbox[2] - bbox[0]
        if line_w > max_width and current_line:
            lines.append(" ".join(current_line))
            current_line = [word]
        else:
            current_line.append(word)
    if current_line:
        lines.append(" ".join(current_line))

    # 렌더링
    total_lines = len(lines)
    start_y = 50 + (140 - total_lines * line_h) // 2
    for i, line in enumerate(lines):
        y = start_y + i * (line_h + 6)
        draw.text(
            (80, y),
            line,
            fill=TEXT_WHITE,
            font=font,
        )

    return img


def make_keyword_label(keyword: str) -> Image.Image:
    """차트 오버레이 시 노출되는 키워드 레이블. RGBA 반환."""
    img = Image.new("RGBA", (400, 60), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 노란색 배경
    draw.rectangle(
        [(0, 0), (400, 60)],
        fill=ACCENT_YELLOW,
    )

    # 검은색 텍스트
    font = load_font(24, bold=True)
    bbox = draw.textbbox((0, 0), keyword, font=font)
    text_w = bbox[2] - bbox[0]
    text_x = (400 - text_w) // 2
    draw.text(
        (text_x, 15),
        keyword,
        fill=(0, 0, 0),
        font=font,
    )

    return img


def make_watermark(channel_name: str) -> Image.Image:
    """채널명 워터마크 (상단 좌측). RGBA 반환."""
    img = Image.new("RGBA", (400, 80), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 파란색 배경 바
    draw.rectangle(
        [(0, 0), (350, 70)],
        fill=(*ACCENT_BLUE, 180),
    )

    # 채널명
    font = load_font(28, bold=True)
    bbox = draw.textbbox((0, 0), channel_name, font=font)
    text_w = bbox[2] - bbox[0]
    text_x = (350 - text_w) // 2
    draw.text(
        (text_x, 20),
        channel_name,
        fill=TEXT_WHITE,
        font=font,
    )

    return img


def make_outro_card(channel_name: str) -> Image.Image:
    """아웃트로 카드. RGBA 반환."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 배경
    draw.rectangle(
        [(0, 0), (WIDTH, HEIGHT)],
        fill=(*BG_DARK, 200),
    )

    # 채널명 (큼)
    channel_font = load_font(80, bold=True)
    bbox = draw.textbbox((0, 0), channel_name, font=channel_font)
    text_w = bbox[2] - bbox[0]
    text_x = (WIDTH - text_w) // 2
    draw.text(
        (text_x, 300),
        channel_name,
        fill=ACCENT_BLUE,
        font=channel_font,
    )

    # 감사 메시지
    thanks_font = load_font(36)
    thanks = "시청해주셔서 감사합니다!"
    bbox = draw.textbbox((0, 0), thanks, font=thanks_font)
    thanks_w = bbox[2] - bbox[0]
    thanks_x = (WIDTH - thanks_w) // 2
    draw.text(
        (thanks_x, 450),
        thanks,
        fill=TEXT_WHITE,
        font=thanks_font,
    )

    # 구독 권유
    subscribe_font = load_font(28)
    subscribe = "채널을 구독하고 알림을 켜세요!"
    bbox = draw.textbbox((0, 0), subscribe, font=subscribe_font)
    sub_w = bbox[2] - bbox[0]
    sub_x = (WIDTH - sub_w) // 2
    draw.text(
        (sub_x, 550),
        subscribe,
        fill=ACCENT_YELLOW,
        font=subscribe_font,
    )

    return img


def make_progress_bar_row(progress: float) -> Image.Image:
    """진행바를 만든다 (0.0 ~ 1.0). 높이는 8px, 폭은 1920px. RGB 반환."""
    img = Image.new("RGB", (WIDTH, 8), BG_DARK)
    draw = ImageDraw.Draw(img)

    # 진행바 (파란색)
    bar_width = int(WIDTH * max(0, min(1, progress)))
    if bar_width > 0:
        draw.rectangle(
            [(0, 0), (bar_width, 8)],
            fill=ACCENT_BLUE,
        )

    return img


def _sample():
    """테스트용 샘플 생성."""
    from pathlib import Path

    out_dir = Path("sample_visuals")
    out_dir.mkdir(exist_ok=True)

    make_title_card("AAPL", "애플 서비스 매출 구조와 마진 변화", "2026년 9월 5일").save(
        out_dir / "title.png"
    )
    make_subtitle("애플의 서비스 부문은 하드웨어보다 마진이 높고, 매 분기 반복적으로 발생하는 구조입니다.").save(
        out_dir / "subtitle.png"
    )
    make_keyword_label("서비스 매출").save(out_dir / "keyword.png")
    make_watermark("머니로직").save(out_dir / "watermark.png")
    make_outro_card("머니로직").save(out_dir / "outro.png")
    make_progress_bar_row(0.5).save(out_dir / "progress_50.png")
    make_background().save(out_dir / "background.png")

    print(f"샘플 생성됨: {out_dir}")


if __name__ == "__main__":
    _sample()
