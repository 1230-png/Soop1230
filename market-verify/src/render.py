"""장면을 화면으로 그리고 ffmpeg 로 영상을 조립한다.

수치를 다루는 채널이라 화면은 건조하게 간다. 자극적인 연출을 넣지 않는 것이
채널 원칙이고, 그건 그대로다.

다만 **어두운 그라데이션 위에 정중앙 큰 글씨**는 자동 생성 영상의 전형이라,
사람이 만든 것으로 보이지 않는다. 그래서 인쇄물 쪽으로 옮겼다 — 미색 종이,
결이 약간 있는 바탕, 왼쪽 정렬, 가는 괘선. 연출을 더한 것이 아니라
'기계가 찍어낸 티'를 뺀 것이다.
"""

import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from src import chart

WIDTH, HEIGHT = 1920, 1080
THUMB_WIDTH, THUMB_HEIGHT = 1280, 720
# 숏폼(세로) 컷용. 롱폼과 같은 그리기 함수를 재사용하려고 크기만 인자로 뺐다.
SHORT_WIDTH, SHORT_HEIGHT = 1080, 1920

# 종이. 순백은 화면에서 눈을 때려서 미색으로 낮춘다.
PAPER = (250, 247, 241)
INK = (26, 25, 22)
MUTED = (140, 134, 121)
RULE = (203, 197, 183)
GRAIN = 6  # 종이 결. 0 이면 완전 평면이라 다시 인쇄물 느낌이 사라진다.
GRAIN_MIX = 0.07  # 더 올리면 종이가 탁해진다.
# 본문 크기는 가로폭에 비례시키되, 세로(숏폼)는 폰에서 보므로 훨씬 키운다.
BODY_RATIO_LANDSCAPE = 0.040
BODY_RATIO_PORTRAIT = 0.092

# 분포 그림
DOT = (92, 88, 79)
ZERO_LINE = (168, 162, 148)
JITTER_ROWS = 5  # 점을 세로로 흩는 단 수. 겹쳐 뭉치면 건수가 적어 보인다.

# 썸네일 아래쪽에 얹는 분포 조각의 자리(세로 비율).
THUMB_STRIP_TOP = 0.66
THUMB_STRIP_BOTTOM = 0.90
# 조각을 얹을 수 있는 제목 줄 수. 이보다 길면 글자가 조각 자리까지 내려온다.
THUMB_STRIP_MAX_TITLE_LINES = 3
# 썸네일 제목 판 (글자 크기, 줄바꿈 폭, 줄 간격). 조각이 들어가면 줄여 잡는다.
THUMB_TITLE = (78, 13, 26)
THUMB_TITLE_WITH_STRIP = (68, 15, 22)

# 느린 확대(켄 번즈). 정지 화면이 몇십 장 이어지면 사람은 '멈춘 영상'으로 본다.
FPS = 30
ZOOM_MAX = 1.07  # 더 당기면 글자가 흐려진다. 눈에 띄면 그것대로 산만하다.
# 1.07 배까지만 당기므로 1.5 배로 미리 키우면 충분하다. 흔히 말하는 2 배는
# 크게 당길 때 이야기고, 여기서는 러너 시간만 먹는다.
ZOOM_PRESCALE = 1.5

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


def _paper(width, height):
    """미색 바탕에 결을 약간 얹는다. 완전한 평면은 화면에서 인쇄물로 안 읽힌다."""
    image = Image.new("RGB", (width, height), PAPER)
    if GRAIN:
        noise = Image.effect_noise((width, height), GRAIN).convert("RGB")
        # 결을 더하되 밝기는 유지한다. multiply 로 섞으면 종이가 회색으로 죽는다.
        image = ImageChops.blend(image, ImageChops.overlay(image, noise), GRAIN_MIX)
    return image


def _draw_block(draw, text, font, top, left, color, wrap, gap):
    """왼쪽 정렬로 여러 줄을 그리고 마지막 y 를 돌려준다.

    가운데 정렬은 자동 생성 영상의 전형이라 왼쪽으로 옮겼다.
    """
    y = top
    for line in textwrap.fill(text, width=wrap).split("\n"):
        draw.text((left, y), line, font=font, fill=color)
        box = draw.textbbox((0, 0), line, font=font)
        y += (box[3] - box[1]) + gap
    return y


def slide(screen_text, section, out_path, source_note=None, width=WIDTH, height=HEIGHT):
    """장면 한 컷. 화면 문구가 주인공이고 섹션 이름은 작게 남긴다.

    width/height 를 바꾸면 그대로 세로(숏폼) 캔버스가 된다 — 그리기 로직은
    가로·세로가 같아서 따로 만들지 않았다.
    """
    portrait = height > width
    image = _paper(width, height)
    draw = ImageDraw.Draw(image)

    margin = int(width * 0.085)
    body_size = int(width * (BODY_RATIO_PORTRAIT if portrait else BODY_RATIO_LANDSCAPE))
    small = max(18, int(body_size * 0.40))
    hairline = max(1, round(width / 960))

    # 머리말: 섹션 이름과 그 아래 가는 괘선. 인쇄물의 난외주 자리다.
    head_y = int(height * (0.07 if portrait else 0.11))
    draw.text((margin, head_y), section, font=_font(small), fill=MUTED)
    rule_y = head_y + int(small * 1.9)
    draw.line([(margin, rule_y), (width - margin, rule_y)], fill=RULE, width=hairline)

    # 본문: 왼쪽 정렬. 한가운데보다 조금 위가 눈에 편하다(시각 중심).
    wrap = 11 if portrait else 17
    body = _font(body_size)
    line_gap = int(body_size * 0.42)
    lines = len(textwrap.fill(screen_text, width=wrap).split("\n"))
    block_height = lines * (body_size + line_gap)
    top = max(rule_y + body_size, (height - block_height) / 2 - height * 0.04)
    _draw_block(draw, screen_text, body, top, margin, INK, wrap, line_gap)

    # 꼬리말: 아래 괘선 하나로 판을 닫는다. 없으면 글자가 허공에 뜬다.
    foot_y = height - int(height * (0.06 if portrait else 0.11))
    draw.line([(margin, foot_y), (width - margin, foot_y)], fill=RULE, width=hairline)
    if source_note:
        draw.text((margin, foot_y + int(small * 0.7)), source_note,
                  font=_font(small), fill=MUTED)
    image.save(out_path)
    return out_path


def distribution_slide(series, caption, section, out_path, source_note=None,
                       width=WIDTH, height=HEIGHT):
    """사례별 수익률을 구간마다 한 줄씩 점으로 흩어 그린다.

    이 채널의 결론은 "평균이 아니라 분포"다. 그런데 분포를 글자로 읽어 주면
    듣는 쪽은 숫자 세 개(중앙값·최저·최고)만 남는다. 점을 흩어 놓으면 어디에
    몰려 있는지가 한 번에 보인다 — 몰린 정도는 말로 옮기기 어려운 종류의 사실이다.

    판은 slide() 와 같다(미색 종이·머리말·괘선). 한 영상 안에서 글자 화면과
    그림 화면이 섞이는데, 판이 다르면 다른 영상을 이어 붙인 것처럼 보인다.
    """
    bounds = chart.span(series)
    if not series or bounds is None:
        raise ValueError("그릴 분포가 없다.")

    data_low, data_high = bounds
    pad = (data_high - data_low) * 0.08 or 1.0
    low, high = data_low - pad, data_high + pad

    portrait = height > width
    image = _paper(width, height)
    draw = ImageDraw.Draw(image)

    margin = int(width * 0.085)
    body_size = int(width * (BODY_RATIO_PORTRAIT if portrait else BODY_RATIO_LANDSCAPE))
    small = max(18, int(body_size * 0.40))
    cap_size = max(small, int(body_size * 0.62))
    hairline = max(1, round(width / 960))
    small_font, cap_font = _font(small), _font(cap_size)

    head_y = int(height * (0.07 if portrait else 0.11))
    draw.text((margin, head_y), section, font=small_font, fill=MUTED)
    rule_y = head_y + int(small * 1.9)
    draw.line([(margin, rule_y), (width - margin, rule_y)], fill=RULE, width=hairline)

    top = rule_y + int(cap_size * 0.9)
    if caption:
        top = _draw_block(
            draw, caption, cap_font, top, margin, INK,
            18 if portrait else 28, int(cap_size * 0.35),
        )

    foot_y = height - int(height * (0.06 if portrait else 0.11))
    plot_top = top + int(cap_size * 0.9)
    plot_bottom = foot_y - int(small * 2.6)  # 가로축 숫자 자리

    gap = int(width * 0.02)
    label_width = max(draw.textlength(name, font=small_font) for name, _ in series)
    plot_left = margin + int(label_width) + gap
    plot_right = width - margin

    def x_of(value):
        return plot_left + (value - low) / (high - low) * (plot_right - plot_left)

    row_height = (plot_bottom - plot_top) / len(series)
    dot = max(3, int(width * 0.0042))

    # 0 선은 줄 전체를 관통한다. 손실 쪽과 이득 쪽이 갈리는 자리라 구간마다
    # 끊으면 눈이 다시 맞춰야 한다.
    zero_x = x_of(0.0)
    draw.line([(zero_x, plot_top), (zero_x, plot_bottom)], fill=ZERO_LINE, width=hairline * 2)

    for index, (name, values) in enumerate(series):
        center_y = plot_top + row_height * (index + 0.5)
        draw.text((plot_left - gap, center_y), name, font=small_font, fill=MUTED, anchor="rm")
        draw.line([(plot_left, center_y), (plot_right, center_y)], fill=RULE, width=hairline)

        # 점이 겹쳐 뭉치면 63건이 10건처럼 보인다. 세로로 조금씩 흩는다.
        # 난수를 쓰지 않는다 — 같은 데이터는 같은 그림이어야 한다.
        for order, value in enumerate(values):
            x = x_of(value)
            y = center_y + ((order % JITTER_ROWS) - (JITTER_ROWS - 1) / 2) * dot * 1.1
            draw.ellipse([x - dot, y - dot, x + dot, y + dot], fill=DOT)

        middle = chart.median(values)
        tick = row_height * 0.30
        tick_x = x_of(middle)
        draw.line(
            [(tick_x, center_y - tick), (tick_x, center_y + tick)],
            fill=INK, width=max(2, hairline * 3),
        )
        label = f"중앙값 {middle:+.1f}%"
        half = draw.textlength(label, font=small_font) / 2
        draw.text(
            (min(max(tick_x, plot_left + half), plot_right - half), center_y - tick - hairline * 3),
            label, font=small_font, fill=INK, anchor="mb",
        )

    # 가로축은 양 끝과 0 만 적는다. 눈금을 촘촘히 넣으면 인쇄물 톤이 깨진다.
    axis_y = plot_bottom + int(small * 0.6)
    for value, anchor in ((data_low, "lt"), (0.0, "mt"), (data_high, "rt")):
        draw.text((x_of(value), axis_y), f"{value:+.0f}%", font=small_font,
                  fill=MUTED, anchor=anchor)

    draw.line([(margin, foot_y), (width - margin, foot_y)], fill=RULE, width=hairline)
    if source_note:
        draw.text((margin, foot_y + int(small * 0.7)), source_note,
                  font=small_font, fill=MUTED)
    image.save(out_path)
    return out_path


def _thumbnail_strip(draw, name, values, left, right, top, bottom):
    """한 구간의 분포를 한 줄로 압축해 그린다.

    썸네일은 목록에서 엄지손톱만 하게 보인다. 읽히는 것은 "점들이 어디에
    몰려 있는가" 하나뿐이라 그것만 남긴다 — 중앙값은 굵은 눈금으로 두고
    숫자를 붙이지 않는다. 폭이 좁아 글자를 더 넣으면 그림이 먼저 안 읽힌다.
    """
    bounds = chart.span([(name, values)])
    if bounds is None:
        return
    data_low, data_high = bounds
    pad = (data_high - data_low) * 0.08 or 1.0
    low, high = data_low - pad, data_high + pad

    small = _font(30)
    draw.text((left, top), f"{chart.short_name(name)} 뒤 · 사례 {len(values)}건",
              font=small, fill=MUTED)

    axis_y = top + 82
    reach = (bottom - top) * 0.28

    def x_of(value):
        return left + (value - low) / (high - low) * (right - left)

    draw.line([(left, axis_y), (right, axis_y)], fill=RULE, width=2)
    zero_x = x_of(0.0)
    draw.line([(zero_x, axis_y - reach), (zero_x, axis_y + reach)], fill=ZERO_LINE, width=3)

    dot = 6
    for order, value in enumerate(values):
        x = x_of(value)
        y = axis_y + ((order % JITTER_ROWS) - (JITTER_ROWS - 1) / 2) * dot * 1.1
        draw.ellipse([x - dot, y - dot, x + dot, y + dot], fill=DOT)

    tick_x = x_of(chart.median(values))
    draw.line([(tick_x, axis_y - reach * 0.9), (tick_x, axis_y + reach * 0.9)],
              fill=INK, width=5)

    # 양 끝과 0 만. 어디부터 어디까지인지 모르면 점이 그냥 무늬가 되고,
    # 0 을 안 적으면 가운데 세로선이 무엇인지 알 수 없다.
    for value, anchor in ((data_low, "lt"), (0.0, "mt"), (data_high, "rt")):
        draw.text((x_of(value), axis_y + reach + 10),
                  "0" if value == 0.0 else f"{value:+.0f}%",
                  font=small, fill=MUTED, anchor=anchor)


def thumbnail(title, out_path, subtitle=None, series=None):
    """제목 썸네일. series 를 주면 아래쪽에 분포 조각을 한 줄 얹는다.

    글자만 있는 썸네일은 추천 목록에서 옆 영상과 구분되지 않는다. 얼굴이나
    빨간 화살표를 쓰지 않는 채널이라 남는 것은 이 영상이 실제로 보여 주는
    것뿐이고, 그게 분포다. **조각의 숫자도 영상 안 그림과 같은 곳(블록)에서
    온다** — 썸네일만 따로 계산하면 눌러 본 사람이 다른 그림을 본다.

    series 가 없으면(전략·토크노믹스 블록) 예전 그대로 글자만 있는 썸네일이다.
    """
    image = _paper(THUMB_WIDTH, THUMB_HEIGHT)
    draw = ImageDraw.Draw(image)

    margin = int(THUMB_WIDTH * 0.085)
    # 블록의 마지막 구간이 가장 긴 기간이다(1개월 · 6개월 · 12개월 순).
    # 짧은 구간은 점이 0 근처에 뭉쳐서 엄지손톱 크기에서 아무것도 안 보인다.
    row = series[-1] if series else None

    # 조각이 들어가면 글자를 작게 잡고 위로 올린다. 가운데 정렬로 두면 겹친다.
    size, wrap, line_gap = THUMB_TITLE_WITH_STRIP if row else THUMB_TITLE
    if row and len(textwrap.fill(title, width=wrap).split("\n")) > THUMB_STRIP_MAX_TITLE_LINES:
        # 제목이 길어 글자가 조각 자리까지 내려온다. 겹쳐 찍거나 아래를 비워 두느니
        # 조각을 포기하고 예전 판(가운데 정렬)으로 돌아간다.
        row = None
        size, wrap, line_gap = THUMB_TITLE

    body = _font(size)
    lines = len(textwrap.fill(title, width=wrap).split("\n"))
    top = (
        int(THUMB_HEIGHT * 0.10) if row
        else (THUMB_HEIGHT - lines * (body.size + line_gap)) / 2 - 20
    )
    end = _draw_block(draw, title, body, top, margin, INK, wrap, line_gap)

    if subtitle:
        rule_y = end + 26
        draw.line([(margin, rule_y), (margin + 150, rule_y)], fill=INK, width=4)
        _draw_block(draw, subtitle, _font(34), rule_y + 24, margin, MUTED, 30, 10)

    if row is not None:
        _thumbnail_strip(draw, row[0], row[1], margin, THUMB_WIDTH - margin,
                         THUMB_HEIGHT * THUMB_STRIP_TOP, THUMB_HEIGHT * THUMB_STRIP_BOTTOM)
    image.save(out_path)
    return out_path


def audio_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def _even(value):
    """yuv420p 는 가로·세로가 짝수여야 한다."""
    return int(value) // 2 * 2


def zoom_filter(width, height, seconds):
    """느린 확대 필터 문자열. 시험이 들여다볼 수 있게 따로 뺐다."""
    # -shortest 가 음성 길이에서 자른다. 그보다 프레임을 넉넉히 잡는 이유는,
    # 모자라게 잡으면 zoompan 이 확대를 처음부터 다시 시작해 화면이 한 번 튀기 때문이다.
    frames = int(round(seconds * FPS)) + FPS
    step = (ZOOM_MAX - 1.0) / frames
    return (
        f"scale={_even(width * ZOOM_PRESCALE)}:{_even(height * ZOOM_PRESCALE)}"
        ":flags=lanczos,"
        f"zoompan=z='min(1+{step:.9f}*on,{ZOOM_MAX})'"
        # 기본값은 왼쪽 위를 향해 당긴다. 글자가 한쪽으로 쏠려 보여서 가운데로 잡는다.
        ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={width}x{height}:fps={FPS},setsar=1"
    )


def mux(image_path, audio_path, out_path, seconds=None, zoom=True):
    """정지 화면 + 음성 → 영상 한 토막.

    seconds 를 주면 화면을 아주 느리게 당긴다. 1.07 배라 보는 사람이 움직임을
    알아채지는 못하지만, 화면이 멈춰 있다는 느낌은 사라진다. 한 편에 정지 화면이
    수십 장 이어지던 자리다.

    **한 영상 안에서는 모든 토막이 같은 길로 가야 한다.** concat 이 다시 인코딩하지
    않고 이어 붙이므로(-c copy), 어떤 토막은 -tune stillimage 로 굳고 어떤 토막은
    아니면 이어 붙인 파일이 깨진다. seconds 를 줄 거면 전부 준다.
    """
    if not zoom or not seconds or seconds <= 0:
        # 길이를 모르면 zoompan 이 몇 프레임을 낼지 정할 수 없다. 예전 길로 간다.
        video_filter, tune = [], ["-tune", "stillimage"]
    else:
        with Image.open(image_path) as source:
            width, height = source.size
        video_filter, tune = ["-vf", zoom_filter(width, height, seconds)], []

    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-loop", "1", "-i", str(image_path),
         "-i", str(audio_path),
         *video_filter,
         "-c:v", "libx264", *tune, "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
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
