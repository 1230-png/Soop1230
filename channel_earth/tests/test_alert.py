"""이벤트 발행 판단을 검사한다. **네트워크도 시계도 타지 않는다.**

시각을 주입해서 검사하는 이유: 냉각 시간과 신선도는 시계에 걸린 규칙이라
`datetime.now()` 를 쓰면 검사가 되지 않는다(혹은 밤 12시에만 깨진다).
"""

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import alert
from lib.sources import Quake

NOW = dt.datetime(2026, 9, 27, 12, 0, tzinfo=dt.timezone.utc)


def quake(mag, hours_ago=1.0, lat=0.0, lon=0.0, qid="q", place="somewhere"):
    return Quake(id=qid, time=NOW - dt.timedelta(hours=hours_ago),
                 lat=lat, lon=lon, depth_km=10.0, mag=mag, place=place)


def empty():
    return {"version": 1, "published": []}


class TestThreshold:
    def test_전세계는_M6_부터(self):
        assert alert.pick_event([quake(6.0)], empty(), NOW)[0] is not None
        assert alert.pick_event([quake(5.9)], empty(), NOW)[0] is None

    def test_한국_일본_인근은_M5_부터(self):
        # 검색 수요는 규모가 아니라 관심에서 난다. 일본 M5.2 는 한국 뉴스에
        # 뜨지만 같은 규모가 남태평양에서 나면 아무 일도 없다.
        near = quake(5.2, lat=35.6, lon=139.7)     # 도쿄 근처
        far = quake(5.2, lat=-20.0, lon=-175.0)    # 통가 근처
        assert alert.near_korea(near.lat, near.lon)
        assert not alert.near_korea(far.lat, far.lon)
        assert alert.pick_event([near], empty(), NOW)[0] is not None
        assert alert.pick_event([far], empty(), NOW)[0] is None

    def test_가장_큰_것을_고른다(self):
        qs = [quake(6.1, qid="a"), quake(6.9, qid="b"), quake(6.3, qid="c")]
        picked, _ = alert.pick_event(qs, empty(), NOW)
        assert picked.id == "b"


class TestFreshness:
    def test_오래된_지진은_내지_않는다(self):
        # 검색이 이미 지나갔고, 늦은 영상은 자리 잡은 뉴스 뒤에 붙는다.
        assert alert.pick_event([quake(6.5, hours_ago=1)], empty(), NOW)[0] is not None
        assert alert.pick_event([quake(6.5, hours_ago=20)], empty(), NOW)[0] is None

    def test_미래_시각은_버린다(self):
        # 피드의 시계가 앞서 있거나 파싱이 틀렸을 때 음수 나이가 나온다.
        assert alert.pick_event([quake(7.5, hours_ago=-3)], empty(), NOW)[0] is None


class TestDedupe:
    def test_이미_낸_지진은_다시_내지_않는다(self):
        state = alert.record(empty(), quake(6.8, qid="done"), NOW)
        picked, why = alert.pick_event([quake(6.8, qid="done")], state, NOW)
        assert picked is None and "없다" in why

    def test_기록은_최근_것만_남는다(self, tmp_path):
        # 이 파일은 커밋되므로 무한히 자라면 안 된다.
        state = empty()
        for i in range(260):
            state = alert.record(state, quake(6.1, qid=f"q{i}"), NOW)
        path = tmp_path / "s.json"
        alert.save_state(path, state)
        assert len(alert.load_state(path)["published"]) == 200


class TestCooldown:
    def test_연달아_내지_않는다(self):
        # 큰 지진은 여진을 수십 개 끌고 온다. 그것마다 한 편씩 내면 같은
        # 틀의 반복 생산이 되고, 그게 유튜브가 거르는 모양이다.
        state = alert.record(empty(), quake(6.8, qid="main"),
                            NOW - dt.timedelta(hours=2))
        picked, why = alert.pick_event([quake(6.2, qid="after")], state, NOW)
        assert picked is None and "냉각" in why

    def test_냉각이_끝나면_낸다(self):
        state = alert.record(empty(), quake(6.8, qid="main"),
                            NOW - dt.timedelta(hours=9))
        assert alert.pick_event([quake(6.2, qid="after")], state, NOW)[0] is not None

    def test_M7_이상은_냉각을_무시한다(self):
        state = alert.record(empty(), quake(6.8, qid="main"),
                            NOW - dt.timedelta(hours=1))
        picked, _ = alert.pick_event([quake(7.4, qid="big")], state, NOW)
        assert picked is not None and picked.id == "big"


class TestState:
    def test_깨진_파일에서_멈추지_않는다(self, tmp_path):
        # 무인으로 도는 코드가 상태 파일 하나 때문에 통째로 멎으면, 고칠
        # 사람이 그 사실을 알 길이 없다. 최악은 한 편 중복이고 그건 보인다.
        path = tmp_path / "broken.json"
        path.write_text("{ 이건 json 이 아니다", encoding="utf-8")
        assert alert.load_state(path) == {"version": 1, "published": []}

    def test_없는_파일도_빈_상태(self, tmp_path):
        assert alert.load_state(tmp_path / "nope.json")["published"] == []

    def test_리스트가_아닌_published_를_고친다(self, tmp_path):
        path = tmp_path / "odd.json"
        path.write_text(json.dumps({"published": "문자열"}), encoding="utf-8")
        assert alert.load_state(path)["published"] == []

    def test_왕복(self, tmp_path):
        path = tmp_path / "s.json"
        alert.save_state(path, alert.record(empty(), quake(6.5, qid="x"), NOW))
        rows = alert.load_state(path)["published"]
        assert len(rows) == 1 and rows[0]["id"] == "x"


class TestReason:
    def test_낼_것이_없어도_이유를_남긴다(self):
        # "아무것도 안 했다"만 남으면 문턱이 잘못 잡힌 것인지 조용한 주였는지
        # 구분할 수 없다.
        _, why = alert.pick_event([quake(3.0)], empty(), NOW)
        assert why and isinstance(why, str)

    def test_낼_때는_문턱을_같이_적는다(self):
        _, why = alert.pick_event([quake(6.4, place="Japan")], empty(), NOW)
        assert "M6.4" in why and "M6.0" in why


class TestRecordWithoutFeed:
    """기록이 피드 없이도 되는지.

    처음에는 업로드 뒤 피드를 다시 받아 그 지진을 찾아 기록했다. 그러면
    **두 번째 조회가 실패하는 순간 기록이 안 남고, 30분 뒤 같은 지진이 또
    나간다** — 업로드는 이미 성공했는데 적을 길이 없어서 생기는 중복이다.
    """

    def test_id_만으로_기록된다(self, tmp_path):
        path = tmp_path / "s.json"
        alert.save_state(path, alert.record_id(empty(), "us7000abcd", NOW,
                                               video_id="vid1"))
        rows = alert.load_state(path)["published"]
        assert rows[0]["id"] == "us7000abcd" and rows[0]["video_id"] == "vid1"

    def test_id_만으로_적어도_중복이_막힌다(self):
        state = alert.record_id(empty(), "us7000abcd", NOW)
        picked, _ = alert.pick_event(
            [quake(6.9, qid="us7000abcd")], state, NOW)
        assert picked is None

    def test_냉각도_id_기록으로_걸린다(self):
        # published_at 만 있으면 냉각 계산이 된다.
        state = alert.record_id(empty(), "earlier", NOW - dt.timedelta(hours=1))
        picked, why = alert.pick_event([quake(6.2, qid="next")], state, NOW)
        assert picked is None and "냉각" in why
