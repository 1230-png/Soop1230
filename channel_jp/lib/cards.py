"""정지 카드. 영상은 이것들을 나레이션에 맞춰 이어 붙인 것이다.

`longform/lib/cards.py`(영어)에서 갈라져 나왔고 두 곳이 다르다.

1. **폰트를 글리프로 고른다.** 원본은 후보 목록에서 존재하는 첫 파일을 썼다.
   그 목록은 나눔고딕이 먼저인데 나눔고딕에는 가나 글리프가 없다. 러너에
   `fonts-nanum` 이 깔려 있으면 일본어가 전부 □ 로 나가고, 예외도 로그도
   없이 나간다.
2. **줄바꿈이 공백에 기대지 않는다.** 원본은 `text.split()` 으로 단어를
   나눴다. 일본어에는 단어 사이 공백이 없어서 긴 문장이 통째로 한 덩어리가
   되고, 줄바꿈 없이 화면 밖으로 흘러 나간다.

이모지는 쓰지 않는다 — 러너 폰트에 글리프가 없어 □ 로 나온다.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1920, 1080

# 밝은 배색. 순백(255,255,255)은 쓰지 않는다 — 자기 전에 트는 영상이라
# 어두운 방에서 화면만 하얗게 타오르면 눈이 아프다. 살짝 따뜻한 off-white 가
# 밝으면서도 밤에 견딜 만하다.
BG = (248, 246, 242)
ACCENT = (14, 108, 140)    # 밝은 바탕에서 읽히려면 충분히 어두워야 한다
BODY = (28, 33, 41)
MUTED = (104, 112, 124)
RULE = (222, 217, 209)
DIM = (176, 172, 165)      # 지금 차례가 아닌 줄. 배경보다는 확실히 진하게

# 가나가 있는 폰트를 앞에 둔다. 그래도 목록 순서만으로는 못 믿는다 —
# 아래 has_kana() 가 실제 글리프를 확인한다.
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# 이 카드가 한 화면에 같이 그리는 문자들. 하나라도 빠지면 그 줄이 □ 가 된다.
# 실제로 이 러너에는 일본어만 있는 폰트(fonts-japanese-gothic)와 한글만 있는
# 폰트(NanumGothic)가 둘 다 있었고, 둘 중 어느 것을 골라도 반쪽이 깨졌다.
SAMPLE_GLYPHS = {
    "히라가나": "あ",
    "가타카나": "ア",
    "한자": "日",
    "한글": "본",
}

# 폰트에 없는 글자를 그릴 때 나오는 모양(.notdef)과 비교하려고 쓴다.
# 사용자 영역(U+E000)이라 어떤 폰트에도 정상 글리프로 들어 있지 않다.
MISSING_GLYPH = "\ue000"


def missing_scripts(path: str) -> list:
    """이 폰트가 못 그리는 문자 종류의 이름들. 빈 목록이면 다 그릴 수 있다.

    목록 순서로 고르면 안 되는 이유가 여기 있다. 파일이 있다는 것과 그 안에
    가나가 있다는 것은 다른 이야기인데, PIL 은 없는 글자를 만나도 예외를
    내지 않고 .notdef(보통 빈 칸이나 네모)를 조용히 그린다.

    그래서 **어떤 폰트에도 없는 글자**를 같이 그려 보고, 픽셀이 같으면 그
    글자도 없는 것으로 본다.
    """
    try:
        font = ImageFont.truetype(path, 48)
    except OSError:
        return list(SAMPLE_GLYPHS)

    def stamp(char: str) -> bytes:
        """글자 하나를 작은 판에 그려 픽셀로 돌려준다."""
        tile = Image.new("L", (64, 64), 0)
        ImageDraw.Draw(tile).text((4, 4), char, font=font, fill=255)
        return tile.tobytes()

    notdef = stamp(MISSING_GLYPH)
    return [name for name, char in SAMPLE_GLYPHS.items()
            if stamp(char) == notdef]


def find_font() -> str:
    """쓸 수 있는 폰트. 없으면 영상을 만들지 않고 멈춘다.

    글리프가 없는 폰트로 그냥 진행하면 35분짜리를 다 만들고 나서 화면이
    전부 □ 인 것을 보게 된다. 그때는 이미 edge-tts 를 450번 부른 뒤다.
    """
    rejected = []
    for path in FONT_CANDIDATES:
        if not Path(path).exists():
            continue
        missing = missing_scripts(path)
        if not missing:
            return path
        rejected.append(f"  {path}\n    없는 문자: {', '.join(missing)}")

    detail = ("\n\n찾긴 했지만 쓸 수 없는 폰트:\n" + "\n".join(rejected)
              if rejected else "")
    raise SystemExit(
        "일본어와 한글을 함께 그릴 수 있는 폰트가 없다. 설치할 것:\n"
        "  sudo apt-get install -y fonts-noto-cjk" + detail
    )


_font_cache: dict = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(find_font(), size)
    return _font_cache[size]


def _wrap(draw, text: str, font, max_width: int) -> list:
    """폭을 재서 줄을 나눈다. 공백이 없으면 글자 단위로 나눈다.

    원본은 `text.split()` 만 썼다. 한국어·영어는 그것으로 되지만 일본어는
    단어 사이에 공백이 없어서 문장 하나가 통째로 한 덩어리가 되고, 나뉘지
    않은 채 화면 밖으로 나간다.

    그래서 공백으로 먼저 나누고, 그렇게 나눈 조각이 그래도 한 줄보다 길면
    글자 단위로 한 번 더 나눈다. 일본어는 어디서 끊어도 읽히므로(가로쓰기에
    금칙 처리가 없어도 카드 한 장으로는 충분하다) 이 정도면 된다.
    """
    lines, line = [], ""
    for chunk in text.split() or [""]:
        trial = f"{line} {chunk}".strip()
        if draw.textlength(trial, font=font) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = chunk
        # 조각 하나가 이미 한 줄을 넘으면 글자 단위로 흘려보낸다.
        while draw.textlength(line, font=font) > max_width and len(line) > 1:
            cut = len(line)
            while cut > 1 and draw.textlength(line[:cut], font=font) > max_width:
                cut -= 1
            lines.append(line[:cut])
            line = line[cut:]
    if line:
        lines.append(line)
    return lines


def _block_height(draw, text, font, max_width, line_gap=14) -> int:
    """그리지 않고 높이만 잰다. 세로 중앙을 맞추려면 먼저 재야 한다."""
    height = 0
    for line in _wrap(draw, text, font, max_width):
        bbox = font.getbbox(line)
        height += (bbox[3] - bbox[1]) + line_gap
    return height


def _centered_block(draw, text, font, top, fill, max_width, line_gap=14) -> int:
    for line in _wrap(draw, text, font, max_width):
        width = draw.textlength(line, font=font)
        bbox = font.getbbox(line)
        draw.text(((WIDTH - width) / 2, top), line, font=font, fill=fill)
        top += (bbox[3] - bbox[1]) + line_gap
    return top


def render(out_path: Path, *, phrase: dict, index: int, total: int,
           stage: str, topic: str = "", brand: str = "귀트는 일본어") -> Path:
    """카드 한 장.

    stage 가 어느 줄에 불을 켤지 정한다 — ja / ko / example / shadow.
    나머지는 어둡게 둔다. 중간에 화면을 본 사람이 지금 무엇을 하는 중인지
    바로 알 수 있어야 한다.

    영어판과 줄 수가 다르다. 한국어 학습자는 **읽기(yomi)** 가 없으면
    일본어 문장을 따라올 수 없어서, 일본어와 뜻 사이에 한 줄이 더 들어간다.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    max_w = WIDTH - 320

    draw.text((80, 54), brand, font=_font(38), fill=MUTED)
    counter = f"{index} / {total}" + (f" · {topic}" if topic else "")
    counter_w = draw.textlength(counter, font=_font(38))
    draw.text((WIDTH - 80 - counter_w, 54), counter, font=_font(38), fill=MUTED)
    draw.line([(80, 120), (WIDTH - 80, 120)], fill=RULE, width=2)

    ja_lit = stage in ("ja", "shadow")
    ko_lit = stage == "ko"
    ex_lit = stage == "example"

    # 그릴 줄을 먼저 모은다: (글, 크기, 색, 위쪽 여백, 줄간격).
    # 재고 나서 그리는 이유는 세로 중앙을 맞추기 위해서다. 예문이 없는 문장과
    # 있는 문장은 높이가 크게 다르고, 수면 팩에는 쉐도잉 안내가 없어서 아래가
    # 통째로 빈다 — 40분 내내 그 상태로 있게 된다.
    blocks = [
        (phrase["ja"], 88, BODY if ja_lit else DIM, 0, 18),
        # 읽기는 일본어 줄과 같이 밝아진다. 소리를 듣는 순간 눈이 가야 할 곳이다.
        (phrase["yomi"], 52, ACCENT if ja_lit else DIM, 18, 14),
        (phrase["ko"], 56,
         BODY if ko_lit else (DIM if not ja_lit else MUTED), 30, 14),
    ]
    divider_after = None
    if phrase.get("ex_ja"):
        divider_after = len(blocks) - 1
        blocks.append((phrase["ex_ja"], 44, BODY if ex_lit else DIM, 84, 14))
        if phrase.get("ex_yomi"):
            blocks.append((phrase["ex_yomi"], 34,
                           ACCENT if ex_lit else DIM, 10, 12))
        if phrase.get("ex_ko"):
            blocks.append((phrase["ex_ko"], 36,
                           MUTED if ex_lit else DIM, 10, 12))

    total_height = sum(
        gap + _block_height(draw, text, _font(size), max_w, line_gap)
        for text, size, _, gap, line_gap in blocks)

    # 쓸 수 있는 세로 구간. 쉐도잉 안내가 뜨는 카드는 그 상자를 피해야 한다.
    top_edge, bottom_edge = 170, HEIGHT - (300 if stage == "shadow" else 110)
    y = max(top_edge, top_edge + (bottom_edge - top_edge - total_height) / 2)

    for position, (text, size, fill, gap, line_gap) in enumerate(blocks):
        y += gap
        if position - 1 == divider_after:
            # 예문 앞의 구분선. 여백 한가운데에 놓는다.
            rule_y = y - gap / 2
            draw.line([(WIDTH / 2 - 180, rule_y), (WIDTH / 2 + 180, rule_y)],
                      fill=RULE, width=2)
        y = _centered_block(draw, text, _font(size), y, fill, max_w, line_gap)

    if stage == "shadow":
        prompt = "따라 말해보세요"
        prompt_w = draw.textlength(prompt, font=_font(52))
        box_y = HEIGHT - 250
        draw.rounded_rectangle(
            [(WIDTH - prompt_w) / 2 - 46, box_y - 24,
             (WIDTH + prompt_w) / 2 + 46, box_y + 72],
            radius=18, outline=ACCENT, width=3)
        draw.text(((WIDTH - prompt_w) / 2, box_y), prompt,
                  font=_font(52), fill=ACCENT)

    # 진행 막대를 두지 않는다. 화면 아래 가로 막대는 재생 바로 읽혀서,
    # 시청자가 영상이 멈춘 줄 알고 화면을 건드리게 된다. 남은 분량은
    # 오른쪽 위 "1 / 150" 이 이미 말해 준다.

    img.save(out_path)
    return out_path


def render_title(out_path: Path, *, lines, subtitle: str = "",
                 brand: str = "귀트는 일본어") -> Path:
    """인트로·아웃트로 카드."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    max_w = WIDTH - 320

    y = 340
    for line in lines:
        y = _centered_block(draw, line, _font(92), y, BODY, max_w, line_gap=22)
        y += 18
    if subtitle:
        y += 40
        _centered_block(draw, subtitle, _font(52), y, ACCENT, max_w)

    brand_w = draw.textlength(brand, font=_font(40))
    draw.text(((WIDTH - brand_w) / 2, HEIGHT - 140), brand,
              font=_font(40), fill=MUTED)
    img.save(out_path)
    return out_path


def render_thumbnail(out_path: Path, *, headline: str, sub: str) -> Path:
    """1280x720 썸네일. 같은 배색이라 같은 채널로 읽힌다."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tw, th = 1280, 720
    img = Image.new("RGB", (tw, th), BG)
    draw = ImageDraw.Draw(img)

    for row in range(th):
        ratio = row / th
        draw.line([(0, row), (tw, row)],
                  fill=(int(248 - 10 * ratio), int(246 - 12 * ratio),
                        int(242 - 14 * ratio)))

    def block(text, size, top, fill):
        font = _font(size)
        for line in _wrap(draw, text, font, tw - 140):
            width = draw.textlength(line, font=font)
            draw.text(((tw - width) / 2, top), line, font=font, fill=fill)
            top += font.getbbox(line)[3] + 16
        return top

    y = block(headline, 88, 170, BODY)
    y += 24
    block(sub, 54, y, ACCENT)

    brand = "귀트는 일본어"
    brand_w = draw.textlength(brand, font=_font(32))
    draw.text((tw - brand_w - 40, th - 60), brand, font=_font(32), fill=MUTED)
    img.save(out_path, quality=92)
    return out_path
