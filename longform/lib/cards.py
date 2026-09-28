"""Still cards rendered with PIL. A long-form video here is nothing but a
sequence of these plus narration, which is what keeps a 70-minute encode
down to a couple of minutes.

Deliberately no emoji anywhere: the runner's font set has no glyphs for them
and they render as tofu boxes (□). Learned the hard way.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1920, 1080

BG = (14, 17, 23)          # #0E1117
ACCENT = (255, 209, 71)    # #FFD147
BODY = (245, 247, 250)     # #F5F7FA
MUTED = (150, 160, 175)    # #96A0AF
RULE = (38, 44, 56)

DIM = (95, 103, 116)       # body text when the stage is not on this line

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",  # local runs on Windows
]


def find_font() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise SystemExit(
        "No usable font found. Install one:\n"
        "  sudo apt-get install -y fonts-nanum fonts-noto-cjk"
    )


_font_cache: dict = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(find_font(), size)
    return _font_cache[size]


def _wrap(draw, text: str, font, max_width: int) -> list:
    """Greedy word wrap measured against the real font, since Korean and
    English differ far too much in width for a fixed character count."""
    words, lines, line = text.split(), [], ""
    for w in words:
        trial = f"{line} {w}".strip()
        if draw.textlength(trial, font=font) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def _centered_block(draw, text, font, top, fill, max_width, line_gap=14) -> int:
    bbox = (0, 0, 0, 0)
    for line in _wrap(draw, text, font, max_width):
        w = draw.textlength(line, font=font)
        bbox = font.getbbox(line)
        draw.text(((WIDTH - w) / 2, top), line, font=font, fill=fill)
        top += (bbox[3] - bbox[1]) + line_gap
    # Ink starts bbox[1] below where a line is drawn. Between lines of one
    # block that offset cancels out, but the block's last line still reaches
    # bbox[1] past `top` — without this the next block overlaps it.
    return top + bbox[1]


def render(out_path: Path, *, phrase: dict, index: int, total: int,
           stage: str, topic: str = "", brand: str = "매일 영어 한마디") -> Path:
    """Draw one card.

    stage picks which line is lit: en / ko / shadow / example. Everything
    else stays dimmed, so a viewer glancing up mid-video can tell instantly
    what they are supposed to be doing right now.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    max_w = WIDTH - 320

    # Top bar
    draw.text((80, 54), brand, font=_font(38), fill=MUTED)
    counter = f"{index} / {total}" + (f" · {topic}" if topic else "")
    cw = draw.textlength(counter, font=_font(38))
    draw.text((WIDTH - 80 - cw, 54), counter, font=_font(38), fill=MUTED)
    draw.line([(80, 120), (WIDTH - 80, 120)], fill=RULE, width=2)

    if stage == "recall":
        # 뜻만 보여 주고 영어는 가린다. 여기서 영어가 보이면 떠올리는 연습이
        # 읽는 연습으로 바뀐다.
        y = _centered_block(draw, phrase["ko"], _font(84), 320, ACCENT, max_w,
                            line_gap=18)
        _centered_block(draw, "? ? ?", _font(92), y + 70, DIM, max_w)
        _prompt(draw, "영어로 말해 보세요")
        _progress(draw, index, total)
        img.save(out_path)
        return out_path

    # Shrink the whole body until it ends above the "따라 말해보세요" box.
    # Every stage of a phrase gets the same scale — measured against the box
    # even when it is not drawn — so the text does not jump between cards.
    scale = 1.0
    while scale > 0.5 and _body(ImageDraw.Draw(Image.new("RGB", (1, 1))),
                                phrase, stage, max_w, scale) > HEIGHT - 300:
        scale -= 0.05
    _body(draw, phrase, stage, max_w, scale)

    if stage == "shadow":
        _prompt(draw, "따라 말해보세요")

    _progress(draw, index, total)
    img.save(out_path)
    return out_path


def _body(draw, phrase: dict, stage: str, max_w: int, scale: float) -> int:
    """Draw the phrase block; returns where it ends."""
    en_lit = stage in ("en", "shadow")
    ko_lit = stage == "ko"
    ex_lit = stage == "example"

    def f(size):
        return _font(round(size * scale))

    def gap(px):
        return round(px * scale)

    y = gap(250) if scale == 1.0 else 170
    y = _centered_block(draw, phrase["en"], f(92), y,
                        BODY if en_lit else DIM, max_w, line_gap=gap(18))
    if phrase.get("pron"):
        # 한글 발음은 영어를 들을 때만 밝힌다. 뜻을 읽는 순간에도 밝으면
        # 눈이 발음 줄에 머물러 영어 문장을 안 본다.
        y += gap(10)
        y = _centered_block(draw, f"[{phrase['pron']}]", f(50), y,
                            MUTED if en_lit else DIM, max_w)
    y += gap(40)
    y = _centered_block(draw, phrase["ko"], f(60), y,
                        ACCENT if ko_lit else (DIM if not en_lit else MUTED), max_w)

    if phrase.get("ex_en"):
        y += gap(60)
        draw.line([(WIDTH / 2 - 180, y), (WIDTH / 2 + 180, y)], fill=RULE, width=2)
        y += gap(50)
        y = _centered_block(draw, phrase["ex_en"], f(46), y,
                            BODY if ex_lit else DIM, max_w)
        if phrase.get("ex_ko"):
            y += gap(14)
            y = _centered_block(draw, phrase["ex_ko"], f(40), y,
                                MUTED if ex_lit else DIM, max_w)
    return y


def _prompt(draw, prompt: str) -> None:
    pw = draw.textlength(prompt, font=_font(56))
    box_y = HEIGHT - 260
    draw.rounded_rectangle(
        [(WIDTH - pw) / 2 - 46, box_y - 26, (WIDTH + pw) / 2 + 46, box_y + 76],
        radius=18, outline=ACCENT, width=3,
    )
    draw.text(((WIDTH - pw) / 2, box_y), prompt, font=_font(56), fill=ACCENT)


def _progress(draw, index: int, total: int) -> None:
    """Progress bar — seeing how much is left measurably reduces drop-off."""
    bar_y = HEIGHT - 90
    draw.rounded_rectangle([80, bar_y, WIDTH - 80, bar_y + 12], radius=6, fill=RULE)
    if total > 0:
        done = 80 + (WIDTH - 160) * (index / total)
        draw.rounded_rectangle([80, bar_y, max(done, 86), bar_y + 12],
                               radius=6, fill=ACCENT)


def render_title(out_path: Path, *, lines, subtitle: str = "",
                 brand: str = "매일 영어 한마디") -> Path:
    """Intro/outro card."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    max_w = WIDTH - 320

    y = 340
    for line in lines:
        y = _centered_block(draw, line, _font(96), y, BODY, max_w, line_gap=22)
        y += 18
    if subtitle:
        y += 40
        _centered_block(draw, subtitle, _font(52), y, ACCENT, max_w)

    bw = draw.textlength(brand, font=_font(40))
    draw.text(((WIDTH - bw) / 2, HEIGHT - 140), brand, font=_font(40), fill=MUTED)
    img.save(out_path)
    return out_path


def render_thumbnail(out_path: Path, *, headline: str, sub: str) -> Path:
    """1280x720 thumbnail. Same palette so it reads as the same channel."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tw, th = 1280, 720
    img = Image.new("RGB", (tw, th), BG)
    draw = ImageDraw.Draw(img)

    for i in range(th):  # subtle vertical lift so it is not a flat block
        t = i / th
        draw.line([(0, i), (tw, i)],
                  fill=(int(14 + 12 * t), int(17 + 14 * t), int(23 + 20 * t)))

    def block(text, size, top, fill):
        f = _font(size)
        words, lines, line = text.split(), [], ""
        for w in words:
            trial = f"{line} {w}".strip()
            if draw.textlength(trial, font=f) <= tw - 140 or not line:
                line = trial
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)
        for ln in lines:
            w = draw.textlength(ln, font=f)
            draw.text(((tw - w) / 2, top), ln, font=f, fill=fill)
            top += f.getbbox(ln)[3] + 16
        return top

    y = block(headline, 92, 170, BODY)
    y += 24
    block(sub, 56, y, ACCENT)

    brand = "매일 영어 한마디 · @200-y3b"
    bw = draw.textlength(brand, font=_font(32))
    draw.text((tw - bw - 40, th - 60), brand, font=_font(32), fill=MUTED)
    img.save(out_path, quality=92)
    return out_path
