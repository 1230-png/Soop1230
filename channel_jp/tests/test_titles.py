"""제목 — 검색어가 앞에 있고, 편마다 다른가.

이 검사가 생긴 이유는 2026-09-27 측정값이다. 이 채널은 롱폼 8편 중 7편이
0회였고, 발행된 제목을 늘어놓고 보니 **같은 제목이 세 편**이었다.

    잠들기 전 일본어 듣기 35분 | 자면서 듣는 일본어 회화 150문장
    잠들기 전 일본어 듣기 35분 | 자면서 듣는 일본어 회화 150문장
    잠들기 전 일본어 듣기 36분 | 자면서 듣는 일본어 회화 150문장

`phrase_count` 가 팩마다 고정이라 예전 틀은 바뀌는 값이 사실상 없었다.
이 파일은 그 상태로 되돌아가는 것을 막는다.
"""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import titles

_CONFIG = yaml.safe_load(
    (Path(__file__).resolve().parent.parent / "packs.yaml").read_text(
        encoding="utf-8"))
PACKS = _CONFIG["packs"]
TOPICS = _CONFIG["topics"]


def phrases(**topic_counts):
    out = []
    for topic, count in topic_counts.items():
        out += [{"topic": topic}] * count
    return out


class TestFocus:
    def test_많이_든_주제부터(self):
        picked = phrases(**{"인사·기본": 40, "식당·카페": 30, "교통·길찾기": 20})
        assert titles.focus_from(picked) == "인사·식당·교통"

    def test_앞말만_쓴다(self):
        # 「인사·기본」을 통째로 이으면 제목이 금방 넘친다.
        assert titles.focus_from(phrases(**{"자기소개·사람": 5})) == "자기소개"

    def test_개수를_제한한다(self):
        picked = phrases(**{"인사·기본": 5, "식당·카페": 4, "교통·길찾기": 3,
                            "감정·반응": 2})
        assert titles.focus_from(picked).count("·") == titles.FOCUS_TOPICS - 1

    def test_같은_입력이_같은_결과를_낸다(self):
        # Counter 의 삽입 순서에 기대면 문장 순서가 제목을 바꾼다.
        a = phrases(**{"인사·기본": 5, "식당·카페": 5})
        b = phrases(**{"식당·카페": 5, "인사·기본": 5})
        assert titles.focus_from(a) == titles.focus_from(b)

    def test_주제가_없으면_빈_값(self):
        # 없는 것을 지어내지 않는다. 부르는 쪽이 그 조각을 뺀다.
        assert titles.focus_from([]) == ""
        assert titles.focus_from([{"topic": None}, {}]) == ""


class TestCompose:
    TEMPLATE = "자면서 듣는 일본어 {count}문장 | {focus} 편 · 흘려듣기 {minutes}분"

    def test_검색어가_맨_앞에_온다(self):
        title = titles.compose(self.TEMPLATE, count=150, minutes=35,
                               focus="인사·식당")
        assert title.startswith("자면서 듣는 일본어")

    def test_focus_가_비면_그_조각을_통째로_버린다(self):
        # 자리만 지우면 「| 편 · 흘려듣기 35분」처럼 뜻 없는 낱말이 남는다.
        title = titles.compose(self.TEMPLATE, count=150, minutes=35, focus="")
        assert "편" not in title and "|" not in title
        assert title == "자면서 듣는 일본어 150문장"

    def test_이미_낸_제목과_겹치면_회차를_붙인다(self):
        first = titles.compose(self.TEMPLATE, count=150, minutes=35,
                               focus="인사·식당")
        second = titles.compose(self.TEMPLATE, count=150, minutes=35,
                                focus="인사·식당", episode=7, taken={first})
        assert second != first and "(7회)" in second

    def test_겹치지_않으면_회차를_붙이지_않는다(self):
        # 회차가 늘 붙으면 제목이 길어지고 검색어 자리를 먹는다.
        title = titles.compose(self.TEMPLATE, count=150, minutes=35,
                               focus="인사·식당", episode=7, taken={"딴 제목"})
        assert "7회" not in title

    def test_상한을_넘으면_뒤_조각을_버린다(self):
        # 글자를 자르면 「…자면서 듣는 일본」으로 끝나 검색에 안 걸린다.
        long_focus = "아주긴주제이름" * 20
        title = titles.compose(self.TEMPLATE, count=150, minutes=35,
                               focus=long_focus)
        assert len(title) <= titles.TITLE_MAX
        assert title.startswith("자면서 듣는 일본어")


class TestEpisodeNumber:
    def test_팩별로_센다(self):
        rows = [{"pack": "sleep_japanese"}, {"pack": "sleep_japanese"},
                {"pack": "shadowing_drill"}]
        assert titles.episode_number(rows, "sleep_japanese") == 3
        assert titles.episode_number(rows, "shadowing_drill") == 2

    def test_기록이_없으면_1회(self):
        assert titles.episode_number([], "sleep_japanese") == 1

    def test_제목_목록은_빈_값을_버린다(self):
        rows = [{"title": "가"}, {"title": ""}, {"title": "  "}, {}]
        assert titles.published_titles(rows) == {"가"}


class TestEveryPackTemplate:
    """packs.yaml 의 모든 틀을 실제로 돌려 본다.

    틀을 손으로 고칠 때 여기가 잡는다 — 검색어를 뒤로 밀거나, 편마다
    바뀌는 값을 빼거나, 상한을 넘기는 것.
    """

    # 제목에 들어가는 것은 내부 이름이 아니라 topics 의 `search` 다.
    # build.py 가 그렇게 넘긴다 — 여기서도 같은 값을 써야 검사가 된다.
    LABEL = TOPICS[0]["search"]

    def _render(self, pack, focus, episode=1, taken=(), topic=None):
        return titles.compose(
            pack["title"], count=pack.get("phrase_count", 30),
            minutes=pack.get("target_minutes", 12),
            topic=topic or self.LABEL, focus=focus, episode=episode,
            taken=taken)

    def test_모든_팩이_상한_안에(self):
        for name, pack in PACKS.items():
            title = self._render(pack, "자기소개·교통·인사")
            assert 0 < len(title) <= titles.TITLE_MAX, name

    def test_모든_팩의_검색어가_앞부분에_있다(self):
        # 검색 결과와 휴대폰 목록에서는 제목 앞부분만 보인다.
        wanted = {
            "sleep_japanese": "자면서 듣는 일본어",
            "sleep_japanese_long": "자면서 듣는 일본어",
            "shadowing_drill": "일본어 쉐도잉",
            "situation_pack": "여행 일본어",
        }
        for name, pack in PACKS.items():
            head = self._render(pack, "인사·식당")[:titles.SEARCH_HEAD]
            assert wanted[name] in head, f"{name}: {head!r}"

    def test_모든_주제의_검색어가_제목_앞에_온다(self):
        """topics 의 `search` 다섯 개를 전부 돌려 본다.

        예전에는 내부 이름이 제목 맨 앞을 먹고 있었다 — 「숙박·문제 해결
        일본어 회화 표현 30개」. 이 팩이 지금 유일하게 도는 롱폼이라
        여기가 닫히면 롱폼 노출이 통째로 닫힌다.
        """
        pack = PACKS["situation_pack"]
        for entry in TOPICS:
            label = entry["search"]
            assert "일본어" in label, entry["name"]
            title = self._render(pack, "인사·식당", topic=label)
            assert title.startswith(label), title
            assert len(title) <= titles.TITLE_MAX

    def test_주제마다_다른_제목이_나온다(self):
        pack = PACKS["situation_pack"]
        rendered = {self._render(pack, "인사·식당", topic=entry["search"])
                    for entry in TOPICS}
        assert len(rendered) == len(TOPICS)

    def test_길이나_문장수만_달라도_제목이_달라진다(self):
        """예전 틀이 깨진 자리다.

        `{count}` 와 `{minutes}` 는 팩마다 고정이라 **그 둘만 쓰면 제목이
        평생 하나**다. 각 팩에서 focus 만 바꿔 서로 다른 제목이 나오는지 본다.
        `situation_pack` 은 {topic} 이 그 역할을 하므로 제외한다.
        """
        for name, pack in PACKS.items():
            if "{focus}" not in pack["title"]:
                continue
            a = self._render(pack, "인사·식당·교통")
            b = self._render(pack, "감정·관광·긴급")
            assert a != b, name

    def test_같은_팩을_여섯_번_내도_제목이_전부_다르다(self):
        for name, pack in PACKS.items():
            seen = set()
            focuses = ["인사·식당", "교통·감정", "인사·식당", "교통·감정",
                       "인사·식당", "교통·감정"]
            for index, focus in enumerate(focuses, start=1):
                title = self._render(pack, focus, episode=index, taken=seen)
                assert title not in seen, f"{name} {index}편: {title!r}"
                seen.add(title)
