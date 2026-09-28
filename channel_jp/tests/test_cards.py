"""카드 배치 — 그림을 눈으로 보지 않고 확인할 수 있는 것들만.

이 파일이 생긴 이유는 @200-y3b 쪽에서 긴 문장의 글자가 「따라 말해보세요」
상자와 겹쳐 나간 것이다(PR #32). 겹침은 영상을 다 만든 뒤에야 보이고,
그때는 이미 ElevenLabs 값을 낸 뒤다.
"""

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from lib import cards

BANK = json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "phrases.json")
    .read_text(encoding="utf-8"))
MAX_W = cards.WIDTH - 320
STAGES = ("ja", "ko", "example", "shadow")
FIELDS = ("ja", "yomi", "ko", "ex_ja", "ex_yomi", "ex_ko")


@pytest.fixture(scope="module")
def draw():
    cards.find_font()       # 폰트가 없으면 여기서 멈춘다 — 그것이 맞다
    return ImageDraw.Draw(Image.new("RGB", (cards.WIDTH, cards.HEIGHT)))


@pytest.fixture(scope="module")
def measured(draw):
    """문장마다 (배율, 그 배율에서의 본문 높이). 은행 전체를 한 번만 잰다 —
    재는 것이 이 파일에서 가장 비싸서, 검사마다 다시 재면 몇 초가 붙는다."""
    out = {}
    for phrase in BANK:
        blocks, _ = cards._blocks_for(phrase, "shadow")
        scale = cards.body_scale(draw, phrase, "shadow", MAX_W)
        out[phrase["id"]] = (scale,
                             cards._body_height(draw, blocks, MAX_W, scale))
    return out


def test_가장_긴_문장도_상자_위에_들어간다(measured):
    """은행의 903문장을 전부 재 본다. 하나라도 넘치면 그 편에서 겹친다."""
    band = cards.BODY_BOTTOM - cards.BODY_TOP
    too_tall = [pid for pid, (_, height) in measured.items() if height > band]
    assert not too_tall, too_tall[:10]


def test_같은_문장의_모든_카드가_같은_배율로_그려진다(draw):
    """배율이 stage 마다 다르면 카드가 넘어갈 때 글자가 위아래로 튄다.
    예전에는 쉐도잉 카드만 상자를 피해서 실제로 그랬다."""
    # 긴 쪽이 줄어드는 쪽이라 거기서만 어긋날 수 있다. 가장 긴 40문장을 본다.
    longest = sorted(BANK, key=lambda p: -sum(len(p.get(k, "")) for k in FIELDS))
    for phrase in longest[:40]:
        scales = {stage: cards.body_scale(draw, phrase, stage, MAX_W)
                  for stage in STAGES}
        assert len(set(scales.values())) == 1, (phrase["id"], scales)


def test_대부분의_문장은_줄이지_않는다(measured):
    """배율이 흔하게 내려가면 기준선이 잘못 잡힌 것이다 — 겹침은 막았는데
    글자만 작아진 영상이 나온다."""
    shrunk = [pid for pid, (scale, _) in measured.items() if scale < 1.0]
    assert len(shrunk) < len(BANK) * 0.2, f"{len(shrunk)}/{len(BANK)}"


def test_반복_훈련_카드는_일본어와_발음을_보여주지_않는다(tmp_path, draw):
    """2부에서 일본어가 보이면 떠올리는 연습이 읽는 연습이 된다. 한글 발음만
    남겨도 같다 — 그것만 읽어도 문장이 그대로 나온다.

    뜻만 같고 나머지가 전부 다른 두 문장을 그려서 **픽셀이 같은지** 본다.
    일본어나 발음이 한 글자라도 찍히면 두 그림이 달라진다. 밝기를 세는 것과
    달리 이 검사에는 넘길 수 있는 문턱이 없다.
    """
    left = {"id": "T1", "ja": "おはようございます。", "yomi": "오하요오 고자이마스",
            "ko": "좋은 아침입니다", "ex_ja": "部長、おはようございます。",
            "ex_yomi": "부초오, 오하요오 고자이마스",
            "ex_ko": "부장님, 좋은 아침입니다."}
    right = dict(left, id="T2", ja="お世話になっております。",
                 yomi="오세와니 낫테 오리마스",
                 ex_ja="いつもお世話になっております。",
                 ex_yomi="이츠모 오세와니 낫테 오리마스",
                 ex_ko="항상 신세 지고 있습니다.")

    def drawn(phrase, stage):
        path = cards.render(tmp_path / f"{phrase['id']}_{stage}.png",
                            phrase=phrase, index=1, total=100, stage=stage,
                            topic="생활 일본어")
        return path.read_bytes()

    assert drawn(left, "recall") == drawn(right, "recall")
    # 검사가 실제로 일본어를 잡아낼 수 있다는 것. 1부 카드에서는 달라야 한다.
    assert drawn(left, "ja") != drawn(right, "ja")


def test_반복_훈련_카드가_뜻은_보여준다(tmp_path, draw):
    """가리는 것은 일본어 쪽이다. 뜻까지 가리면 떠올릴 단서가 없다."""
    base = {"id": "T1", "ja": "はい。", "yomi": "하이", "ko": "네",
            "ex_ja": "はい、そうです。", "ex_yomi": "하이, 소오데스",
            "ex_ko": "네, 그렇습니다."}

    def drawn(ko):
        path = cards.render(tmp_path / f"{ko}.png", phrase=dict(base, ko=ko),
                            index=1, total=100, stage="recall", topic="")
        return path.read_bytes()

    assert drawn("네") != drawn("아니요")
