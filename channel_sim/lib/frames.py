"""화면을 그린다. PIL 이 아니라 numpy 로.

PIL 로 막대 256개를 매 프레임 그리면 20분짜리(36,000프레임)에서 그리기만
몇십 분이 든다. 막대는 결국 직사각형이라, 색 배열 하나를 브로드캐스트하면
한 번의 연산으로 끝난다 — 프레임당 1밀리초 아래로 떨어진다.

글자는 여전히 PIL 이 필요하다(numpy 로 한글을 그릴 수는 없다). 대신 글자는
거의 변하지 않으므로 **꼭지마다 한 번 그려 두고 픽셀을 복사**한다. 매 프레임
바뀌는 것은 숫자 몇 개뿐이라 그 부분만 작은 조각으로 다시 그린다.
"""

from __future__ import annotations

import colorsys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1920, 1080

BG = (10, 12, 18)
FG = (226, 232, 240)
DIM = (120, 132, 150)
EDGE = (32, 38, 50)
COMPARE = (255, 255, 255)   # 지금 비교 중인 칸
WRITE = (255, 92, 92)       # 방금 값이 바뀐 칸
DONE = (74, 222, 128)       # 다 끝났을 때

KR_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]
KR_BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
]
MONO_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
]

# 막대가 그려지는 자리. 위에 머리글, 아래에 진행 바가 들어갈 만큼 비워 둔다.
BAR_TOP, BAR_BOTTOM = 250, 940
BAR_LEFT, BAR_RIGHT = 120, 1800

# 숫자가 들어가는 자리. 매 프레임 다시 그리는 유일한 곳이라 좌표를 고정한다.
COUNTER_BOX = (1180, 150, 1800, 215)


def _pick(candidates: list[str]) -> str:
    for path in candidates:
        if Path(path).exists():
            return path
    raise RuntimeError(f"글꼴을 찾지 못했다: {candidates}")


def kr_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_pick(KR_BOLD_CANDIDATES if bold else KR_CANDIDATES), size)


def mono_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_pick(MONO_CANDIDATES), size)


def value_colors(n: int) -> np.ndarray:
    """값 1..n 을 무지개로. 정렬이 끝나면 화면이 깨끗한 그라데이션이 된다.

    이게 이 영상의 시각적 보상이다. 단색 막대로 그리면 끝났는지 아닌지를
    높이만 보고 판단해야 하는데, 색을 얹으면 **어질러진 정도가 그대로
    보인다** — 아직 섞여 있는 구간이 색의 불연속으로 드러난다.

    채도와 밝기를 최대로 두지 않는 이유는 유튜브 재인코딩 때문이다. 쨍한
    빨강과 파랑이 붙어 있으면 색 경계가 뭉개져 띠가 진다.
    """
    hues = np.linspace(0.0, 0.85, n)
    table = [colorsys.hsv_to_rgb(h, 0.72, 0.95) for h in hues]
    return (np.array(table) * 255).astype(np.uint8)


class Chrome:
    """꼭지 하나 동안 변하지 않는 화면. 한 번 그려 두고 프레임마다 복사한다."""

    def __init__(self, title: str, subtitle: str, index: str = "") -> None:
        img = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)

        if index:
            draw.text((120, 96), index, font=kr_font(30, bold=True), fill=(96, 165, 250))
        draw.text((120, 140), title, font=kr_font(64, bold=True), fill=FG)
        draw.text((124, 220), subtitle, font=kr_font(32), fill=DIM)

        # 막대 자리 아래를 받치는 선. 막대가 허공에 뜬 것처럼 보이지 않게 한다.
        draw.line([BAR_LEFT, BAR_BOTTOM + 2, BAR_RIGHT, BAR_BOTTOM + 2],
                  fill=EDGE, width=3)

        self.base = np.asarray(img, dtype=np.uint8).copy()


def draw_bars(frame: np.ndarray, values: np.ndarray, colors: np.ndarray,
              marks: dict[int, tuple] | None = None) -> None:
    """막대를 그린다. 프레임을 제자리에서 고친다.

    `marks` 는 지금 만지고 있는 칸이다. 이 표시가 없으면 무엇이 일어나는지
    따라갈 수가 없다 — 특히 비교만 하고 값이 안 바뀌는 순간은 표시가
    없으면 화면이 정지한 것과 구분되지 않는다.
    """
    n = len(values)
    span = BAR_RIGHT - BAR_LEFT
    bar_w = max(1, span // n)
    used = bar_w * n
    x0 = BAR_LEFT + (span - used) // 2
    height = BAR_BOTTOM - BAR_TOP

    col = colors[values - 1].copy()
    if marks:
        for index, color in marks.items():
            if 0 <= index < n:
                col[index] = color

    tops = (height - (values / values.max() * height)).astype(np.int32)
    rows = np.arange(height, dtype=np.int32)[:, None]
    mask = rows >= tops[None, :]

    field = np.where(mask[:, :, None], col[None, :, :],
                     np.array(BG, dtype=np.uint8)[None, None, :])
    wide = np.repeat(field, bar_w, axis=1)
    frame[BAR_TOP:BAR_BOTTOM, x0:x0 + used] = wide


def draw_progress(frame: np.ndarray, ratio: float,
                  color: tuple = (96, 165, 250)) -> None:
    """아래쪽 진행 바. 롱폼에서 이게 없으면 얼마나 남았는지 알 수 없다.

    유튜브 재생 바는 마우스를 올려야 보인다. 끝이 보이면 끝까지 본다 —
    앞 채널의 쇼츠에서도 같은 이유로 넣었던 장치다.
    """
    y0, y1 = HEIGHT - 70, HEIGHT - 58
    frame[y0:y1, BAR_LEFT:BAR_RIGHT] = EDGE
    end = BAR_LEFT + int((BAR_RIGHT - BAR_LEFT) * max(0.0, min(1.0, ratio)))
    if end > BAR_LEFT:
        frame[y0:y1, BAR_LEFT:end] = color


def counter_patch(compares: int, writes: int) -> np.ndarray:
    """오른쪽 위 숫자판. 매 프레임 바뀌는 유일한 글자."""
    x0, y0, x1, y1 = COUNTER_BOX
    img = Image.new("RGB", (x1 - x0, y1 - y0), BG)
    draw = ImageDraw.Draw(img)
    font = mono_font(38)
    label = kr_font(26)
    draw.text((0, 12), "비교", font=label, fill=DIM)
    draw.text((66, 4), f"{compares:>9,}", font=font, fill=FG)
    draw.text((330, 12), "쓰기", font=label, fill=DIM)
    draw.text((396, 4), f"{writes:>8,}", font=font, fill=WRITE)
    return np.asarray(img, dtype=np.uint8)


def paste(frame: np.ndarray, patch: np.ndarray, box: tuple) -> None:
    x0, y0, x1, y1 = box
    frame[y0:y1, x0:x1] = patch


def text_card(lines: list[tuple[str, int, bool, tuple]], gap: int = 28) -> np.ndarray:
    """가운데 정렬된 글자 카드. 여는 화면과 순위표에 쓴다.

    `lines` 는 (글, 크기, 굵게, 색) 이다. 서식을 데이터로 받는 이유는
    카드 종류마다 함수를 따로 두면 금방 열 개가 되기 때문이다.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    heights = []
    for text, size, bold, _ in lines:
        font = kr_font(size, bold)
        heights.append(draw.textbbox((0, 0), text or "M", font=font)[3] + gap)
    y = (HEIGHT - sum(heights)) / 2

    for (text, size, bold, color), h in zip(lines, heights):
        if text:
            font = kr_font(size, bold)
            box = draw.textbbox((0, 0), text, font=font)
            draw.text(((WIDTH - (box[2] - box[0])) / 2, y - box[1]), text,
                      font=font, fill=color)
        y += h

    return np.asarray(img, dtype=np.uint8).copy()


def table_card(title: str, note: str, rows: list[tuple[str, str]],
               highlight: int = 3) -> np.ndarray:
    """순위표. 이름은 왼쪽, 숫자는 오른쪽 끝에 맞춘다.

    가운데 정렬로 두면 숫자의 자릿수가 제각각이라 **크기를 눈으로 비교할 수
    없다.** 73,536 과 2,819 가 한눈에 몇 배인지 보이는 것이 이 카드의 전부라,
    자릿수를 세로로 맞추는 것이 서식이 아니라 내용이다.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    name_font = kr_font(36)
    name_bold = kr_font(36, bold=True)
    num_font = mono_font(36)
    rank_font = mono_font(30)

    line_h = 58
    block = len(rows) * line_h
    top = (HEIGHT - block) / 2 + 60

    head = kr_font(64, bold=True)
    box = draw.textbbox((0, 0), title, font=head)
    draw.text(((WIDTH - (box[2] - box[0])) / 2, top - 210), title,
              font=head, fill=FG)
    sub = kr_font(30)
    box = draw.textbbox((0, 0), note, font=sub)
    draw.text(((WIDTH - (box[2] - box[0])) / 2, top - 120), note,
              font=sub, fill=DIM)

    left, right = 620, 1300
    for rank, (name, value) in enumerate(rows, 1):
        y = top + (rank - 1) * line_h
        top3 = rank <= highlight
        color = DONE if top3 else FG
        draw.text((left - 80, y + 4), f"{rank:>2}", font=rank_font, fill=DIM)
        draw.text((left, y), name, font=name_bold if top3 else name_font,
                  fill=color)
        box = draw.textbbox((0, 0), value, font=num_font)
        draw.text((right - (box[2] - box[0]), y), value, font=num_font,
                  fill=color)

    return np.asarray(img, dtype=np.uint8).copy()
