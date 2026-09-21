"""화면 카드 렌더링.

앞 채널의 가장 큰 결함은 개발 채널인데 화면에 코드가 한 줄도 없었다는 것이다.
말로만 하는 30분은 끝까지 볼 이유가 없다. 여기서는 카드가 다섯 종류다.

    title     한 편의 표지
    talk      요점 몇 줄. 코드가 필요 없는 구간
    code      문법 하이라이팅된 코드. 줄 강조 가능
    terminal  명령과 그 출력
    diagram   메모리 배치·흐름·비교표

코드는 ASCII 로만 쓴다. PIL 은 글자마다 폰트를 바꿔 주지 않아서 고정폭 폰트에
없는 한글이 섞이면 그 자리가 네모로 깨진다. 한국어 설명은 카드 아래 캡션
띠에 따로 싣는다 — 실제 코드에 한글 식별자를 쓰지도 않으니 손해가 없다.
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import get_lexer_by_name
from pygments.token import Token

WIDTH, HEIGHT = 1920, 1080

# GitHub 어두운 배경 계열. 개발자가 하루 종일 보는 색이라 낯설지 않고,
# 흰 바탕보다 유튜브 재인코딩 뒤 글자 경계가 덜 뭉갠다.
BG = (13, 17, 23)
PANEL = (22, 27, 34)
PANEL_EDGE = (48, 54, 61)
FG = (201, 209, 217)
DIM = (125, 133, 144)
ACCENT = (88, 166, 255)
GOOD = (63, 185, 80)
WARN = (210, 153, 34)
HILITE = (28, 42, 64)  # 강조된 줄의 배경

MONO_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]
MONO_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
]
KR_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]
KR_BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
]

# 토큰을 색으로. Pygments 의 formatter 를 쓰지 않고 직접 칠하는 이유는
# 글자 위치를 우리가 잡아야 줄 강조와 캡션 띠를 같이 얹을 수 있기 때문이다.
TOKEN_COLORS = [
    (Token.Comment, (139, 148, 158)),
    (Token.Keyword, (255, 123, 114)),
    (Token.Name.Function, (210, 168, 255)),
    (Token.Name.Class, (210, 168, 255)),
    (Token.Name.Builtin, (121, 192, 255)),
    (Token.String, (165, 214, 255)),
    (Token.Number, (121, 192, 255)),
    (Token.Operator, (255, 123, 114)),
    (Token.Error, (248, 81, 73)),
]


def _pick(candidates: list[str]) -> str:
    for path in candidates:
        if os.path.exists(path):
            return path
    raise RuntimeError(f"폰트를 찾지 못했다: {candidates}")


def mono_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(
        _pick(MONO_BOLD_CANDIDATES if bold else MONO_CANDIDATES), size
    )


def kr_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(
        _pick(KR_BOLD_CANDIDATES if bold else KR_CANDIDATES), size
    )


def token_color(ttype) -> tuple:
    """토큰 종류에서 색을 찾는다. 하위 종류는 상위 것을 물려받는다."""
    for base, color in TOKEN_COLORS:
        if ttype in base:
            return color
    return FG


def _base(chip: str = "") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """모든 카드가 공유하는 바탕. 칩은 지금 어느 꼭지인지 알려 준다."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    if chip:
        font = kr_font(30, bold=True)
        bbox = draw.textbbox((0, 0), chip, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.rounded_rectangle(
            [72, 56, 72 + w + 56, 56 + h + 30], radius=(h + 30) // 2, fill=PANEL,
            outline=PANEL_EDGE, width=2,
        )
        draw.text((100, 56 + 15 - bbox[1]), chip, font=font, fill=ACCENT)
    return img, draw


def _caption(draw: ImageDraw.ImageDraw, text: str) -> None:
    """카드 아래 한국어 한 줄.

    코드가 ASCII 라서 화면만 봐서는 무엇을 보라는 것인지 알 수 없다. 이 줄이
    "지금 이 코드에서 볼 곳"을 말해 준다.
    """
    if not text:
        return
    font = kr_font(38)
    lines = _wrap_kr(draw, text, font, WIDTH - 200)[:2]
    y = HEIGHT - 60 - len(lines) * 52
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        draw.text(((WIDTH - (bbox[2] - bbox[0])) / 2, y), line, font=font, fill=DIM)
        y += 52


def _wrap_kr(draw, text: str, font, max_width: int) -> list[str]:
    """한국어 줄바꿈. 어절 단위로 끊는다."""
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if cur and draw.textlength(trial, font=font) > max_width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines or [text]


# --------------------------------------------------------------------------
# 카드
# --------------------------------------------------------------------------


def render_title(out: Path, *, title: str, hook: str, season: str, number: str) -> Path:
    img, draw = _base()

    label = f"{season} · {number}"
    lf = kr_font(34, bold=True)
    bbox = draw.textbbox((0, 0), label, font=lf)
    draw.text(((WIDTH - (bbox[2] - bbox[0])) / 2, 300), label, font=lf, fill=ACCENT)

    tf = kr_font(96, bold=True)
    lines = _wrap_kr(draw, title, tf, WIDTH - 360)
    y = 400
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=tf)
        draw.text(((WIDTH - (bbox[2] - bbox[0])) / 2, y), line, font=tf, fill=FG)
        y += 124

    draw.rounded_rectangle([(WIDTH - 140) / 2, y + 40, (WIDTH + 140) / 2, y + 48],
                           radius=4, fill=ACCENT)

    hf = kr_font(42)
    bbox = draw.textbbox((0, 0), hook, font=hf)
    draw.text(((WIDTH - (bbox[2] - bbox[0])) / 2, y + 96), hook, font=hf, fill=DIM)

    img.save(out)
    return out


def render_talk(out: Path, *, chip: str, heading: str, points: list[str]) -> Path:
    """코드가 필요 없는 구간. 요점만 띄운다."""
    img, draw = _base(chip)

    hf = kr_font(64, bold=True)
    y = 220
    for line in _wrap_kr(draw, heading, hf, WIDTH - 240):
        draw.text((120, y), line, font=hf, fill=FG)
        y += 86

    pf = kr_font(44)
    y += 40
    for point in points[:5]:
        draw.ellipse([124, y + 20, 140, y + 36], fill=ACCENT)
        for i, line in enumerate(_wrap_kr(draw, point, pf, WIDTH - 340)[:2]):
            draw.text((176, y), line, font=pf, fill=FG if i == 0 else DIM)
            y += 58
        y += 22

    img.save(out)
    return out


def render_code(out: Path, *, chip: str, lang: str, code: str,
                highlight: list[int] | None = None, caption: str = "") -> Path:
    """문법 하이라이팅된 코드 한 판.

    highlight 는 1부터 세는 줄 번호다. 강조한 줄만 배경을 밝혀서, 내레이션이
    "여기"라고 말할 때 눈이 갈 곳을 만든다.
    """
    img, draw = _base(chip)
    highlight = highlight or []

    raw_lines = code.rstrip("\n").split("\n")

    # 글자 크기를 줄 수가 아니라 남은 높이에서 정한다. 줄 수로만 정하면
    # 긴 코드에서 패널이 캡션 띠를 덮어쓴다 — 실제로 12줄짜리에서 그랬다.
    top, bottom = 170, HEIGHT - (190 if caption else 90)
    avail = bottom - top
    pad, gutter = 44, 72
    size = 38
    while size > 18:
        line_h = int(size * 1.62)
        if len(raw_lines) * line_h + pad * 2 <= avail:
            break
        size -= 2

    font = mono_font(size)
    line_h = int(size * 1.62)
    char_w = draw.textlength("M", font=font)

    body_w = int(max(draw.textlength(l, font=font) for l in raw_lines) + char_w * 2)
    panel_w = min(WIDTH - 200, gutter + body_w + pad * 2)
    panel_h = len(raw_lines) * line_h + pad * 2
    x0 = (WIDTH - panel_w) / 2
    y0 = top + max(0, (avail - panel_h) / 2)

    draw.rounded_rectangle([x0, y0, x0 + panel_w, y0 + panel_h], radius=18,
                           fill=PANEL, outline=PANEL_EDGE, width=2)

    # 토큰을 줄별로 모아 둔다. Pygments 는 줄바꿈을 토큰에 섞어서 내보낸다.
    lexer = get_lexer_by_name(lang, stripnl=False)
    per_line: list[list[tuple]] = [[]]
    for ttype, value in lex(code.rstrip("\n"), lexer):
        parts = value.split("\n")
        for i, piece in enumerate(parts):
            if piece:
                per_line[-1].append((ttype, piece))
            # 마지막 조각 뒤에는 줄바꿈이 없다. 여기서 인덱스를 쓰지 않고
            # 값을 비교하면 같은 글자가 반복될 때 줄이 엉킨다.
            if i < len(parts) - 1:
                per_line.append([])
    while len(per_line) < len(raw_lines):
        per_line.append([])

    num_font = mono_font(size - 6)
    for idx, tokens in enumerate(per_line[: len(raw_lines)]):
        y = y0 + pad + idx * line_h
        if idx + 1 in highlight:
            draw.rectangle([x0 + 2, y - 6, x0 + panel_w - 2, y + line_h - 6], fill=HILITE)
            draw.rectangle([x0 + 2, y - 6, x0 + 8, y + line_h - 6], fill=ACCENT)

        draw.text((x0 + pad, y + 4), f"{idx + 1:>2}", font=num_font, fill=DIM)
        x = x0 + pad + gutter
        for ttype, text in tokens:
            draw.text((x, y), text, font=font, fill=token_color(ttype))
            x += draw.textlength(text, font=font)

    _caption(draw, caption)
    img.save(out)
    return out


def render_terminal(out: Path, *, chip: str, command: str, output: str,
                    caption: str = "") -> Path:
    """명령 한 줄과 그 출력.

    코드보다 이쪽이 설득력이 있을 때가 많다. 주장이 아니라 기계가 찍은
    값이기 때문이다.
    """
    img, draw = _base(chip)

    lines = output.rstrip("\n").split("\n")

    # 코드 카드와 같은 이유로 남은 높이에서 글자 크기를 정한다.
    top, bottom = 170, HEIGHT - (190 if caption else 90)
    avail = bottom - top
    pad, bar = 40, 52
    size = 34
    while size > 16:
        line_h = int(size * 1.6)
        if bar + (len(lines) + 2) * line_h + pad * 2 <= avail:
            break
        size -= 2

    font = mono_font(size)
    line_h = int(size * 1.6)
    widest = max([command, *lines], key=len)
    panel_w = min(WIDTH - 200, int(draw.textlength(widest, font=font)) + pad * 2 + 60)
    panel_h = bar + (len(lines) + 2) * line_h + pad * 2
    x0 = (WIDTH - panel_w) / 2
    y0 = top + max(0, (avail - panel_h) / 2)

    draw.rounded_rectangle([x0, y0, x0 + panel_w, y0 + panel_h], radius=18,
                           fill=(10, 13, 18), outline=PANEL_EDGE, width=2)
    draw.rounded_rectangle([x0, y0, x0 + panel_w, y0 + bar], radius=18, fill=PANEL)
    draw.rectangle([x0, y0 + bar - 18, x0 + panel_w, y0 + bar], fill=PANEL)
    for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        draw.ellipse([x0 + 24 + i * 28, y0 + 18, x0 + 38 + i * 28, y0 + 32], fill=color)

    y = y0 + bar + pad
    draw.text((x0 + pad, y), "$", font=mono_font(size, bold=True), fill=GOOD)
    draw.text((x0 + pad + draw.textlength("$ ", font=font), y), command,
              font=mono_font(size, bold=True), fill=FG)
    y += line_h * 2

    for line in lines:
        # 값이 튀는 줄은 눈에 띄게 둔다. 숫자를 읽으라고 띄운 화면이다.
        color = WARN if any(k in line for k in ("error", "Error", "killed", "Killed")) else DIM
        draw.text((x0 + pad, y), line, font=font, fill=color)
        y += line_h

    _caption(draw, caption)
    img.save(out)
    return out


def render_diagram(out: Path, *, chip: str, kind: str, rows: list[dict],
                   caption: str = "") -> Path:
    """선언적 도식.

    범용 그리기 엔진을 만들지 않는다. 이 커리큘럼이 실제로 필요로 하는 세
    가지만 둔다 — 메모리처럼 위아래로 쌓인 띠, 흐름을 나타내는 상자 줄,
    좌우 비교표. 그 밖이 필요해지면 그때 늘린다.
    """
    img, draw = _base(chip)

    if kind == "stack":
        # 메모리 배치. 위가 높은 주소다.
        band_h = min(120, int(640 / max(len(rows), 1)))
        total = band_h * len(rows)
        x0, x1 = 460, WIDTH - 460
        y = (HEIGHT - 140 - total) / 2
        for row in rows:
            fill = PANEL if not row.get("accent") else (30, 52, 82)
            draw.rectangle([x0, y, x1, y + band_h], fill=fill, outline=PANEL_EDGE, width=2)
            lf = kr_font(40, bold=True)
            draw.text((x0 + 36, y + band_h / 2 - 26), row["label"], font=lf,
                      fill=ACCENT if row.get("accent") else FG)
            if row.get("note"):
                nf = kr_font(30)
                nb = draw.textbbox((0, 0), row["note"], font=nf)
                draw.text((x1 - 36 - (nb[2] - nb[0]), y + band_h / 2 - 20),
                          row["note"], font=nf, fill=DIM)
            y += band_h

    elif kind == "flow":
        # 흐름. 상자와 화살표.
        n = len(rows)
        box_w, box_h, gap = 300, 160, 90
        total = n * box_w + (n - 1) * gap
        x = (WIDTH - total) / 2
        y = (HEIGHT - 140 - box_h) / 2
        for i, row in enumerate(rows):
            fill = (30, 52, 82) if row.get("accent") else PANEL
            draw.rounded_rectangle([x, y, x + box_w, y + box_h], radius=14,
                                   fill=fill, outline=PANEL_EDGE, width=2)
            lf = kr_font(36, bold=True)
            for j, line in enumerate(_wrap_kr(draw, row["label"], lf, box_w - 40)[:2]):
                lb = draw.textbbox((0, 0), line, font=lf)
                draw.text((x + (box_w - (lb[2] - lb[0])) / 2, y + 44 + j * 46),
                          line, font=lf, fill=ACCENT if row.get("accent") else FG)
            if i < n - 1:
                ax = x + box_w + 18
                draw.line([ax, y + box_h / 2, ax + gap - 36, y + box_h / 2],
                          fill=DIM, width=3)
                draw.polygon([(ax + gap - 36, y + box_h / 2 - 10),
                              (ax + gap - 36, y + box_h / 2 + 10),
                              (ax + gap - 16, y + box_h / 2)], fill=DIM)
            x += box_w + gap

    elif kind == "compare":
        # 좌우 비교. 가운데 선으로 가른다.
        mid = WIDTH / 2
        draw.line([mid, 220, mid, HEIGHT - 220], fill=PANEL_EDGE, width=2)
        hf, bf = kr_font(46, bold=True), kr_font(36)
        for side, key in ((0, "left"), (1, "right")):
            cx = mid / 2 + side * mid
            head = rows[0][key] if rows else ""
            hb = draw.textbbox((0, 0), head, font=hf)
            draw.text((cx - (hb[2] - hb[0]) / 2, 250), head, font=hf,
                      fill=ACCENT if side else FG)
            y = 360
            for row in rows[1:]:
                for line in _wrap_kr(draw, row[key], bf, mid - 160)[:2]:
                    lb = draw.textbbox((0, 0), line, font=bf)
                    draw.text((cx - (lb[2] - lb[0]) / 2, y), line, font=bf, fill=DIM)
                    y += 50
                y += 24

    else:
        raise ValueError(f"모르는 도식 종류: {kind}")

    _caption(draw, caption)
    img.save(out)
    return out


def render_thumbnail(out: Path, *, title: str, hook: str, number: str) -> Path:
    """썸네일. 제목이 문장 중간에서 잘리지 않게 글자 수를 먼저 줄인다.

    앞 채널이 "…길목마다", "…커널 내부 소켓" 처럼 잘린 제목을 달고 있었고,
    사용자가 "AI스럽다"고 느낀 실제 원인이 이쪽이었다.
    """
    img, draw = _base()

    nf = kr_font(40, bold=True)
    draw.rounded_rectangle([90, 90, 300, 160], radius=14, fill=ACCENT)
    nb = draw.textbbox((0, 0), number, font=nf)
    draw.text((195 - (nb[2] - nb[0]) / 2, 108), number, font=nf, fill=BG)

    tf = kr_font(132, bold=True)
    lines = _wrap_kr(draw, title, tf, WIDTH - 200)
    if len(lines) > 2:  # 세 줄이면 읽히지 않는다. 작게 줄여 두 줄로 맞춘다.
        tf = kr_font(104, bold=True)
        lines = _wrap_kr(draw, title, tf, WIDTH - 200)[:2]
    y = (HEIGHT - len(lines) * 158) / 2
    for line in lines:
        draw.text((100, y), line, font=tf, fill=FG)
        y += 158

    hf = kr_font(46)
    draw.text((100, y + 24), hook, font=hf, fill=ACCENT)

    img.save(out)
    return out
