"""응답 파싱. **네트워크를 타지 않는다** — 픽스처만 읽는다.

이 검사가 특히 중요한 이유: 이 저장소를 만든 컨테이너에서 USGS 에 닿지
못했다(egress 403). 그래서 파서는 실제 응답이 아니라 **문서로 공개된
스키마를 보고 쓴 것**이고, 여기서 잡히는 것은 "우리가 생각한 형식대로
왔을 때 제대로 읽는가"까지다. 실제 형식이 다르면 첫 Actions 실행의
--dump 에서 잡아야 한다.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib import sources  # noqa: E402

FIXTURE = ROOT / "data" / "fixtures" / "usgs_day_synthetic.json"


@pytest.fixture(scope="module")
def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_픽스처를_읽는다(payload):
    quakes = sources.parse_quakes(payload)
    assert quakes
    assert all(-90 <= q.lat <= 90 for q in quakes)
    assert all(-180 <= q.lon <= 180 for q in quakes)
    assert all(q.depth_km >= 0 for q in quakes)


def test_시간순으로_돌려준다(payload):
    """타임랩스가 이 순서를 그대로 믿는다. 뒤섞여 오면 시계가 거꾸로 간다."""
    quakes = sources.parse_quakes(payload)
    assert all(a.time <= b.time for a, b in zip(quakes, quakes[1:]))


def test_규모가_없는_줄은_버린다(payload):
    """자동 검출 직후라 규모가 아직 없는 줄이 실제로 온다.

    0 으로 치면 지도에 점이 찍히고 통계가 틀어진다.
    """
    total = len(payload["features"])
    kept = len(sources.parse_quakes(payload))
    nulls = sum(1 for f in payload["features"]
                if f["properties"].get("mag") is None)
    assert nulls > 0, "픽스처에 규모 없는 줄이 있어야 이 검사가 뜻이 있다"
    assert kept == total - nulls


def test_features_가_없으면_멈춘다():
    with pytest.raises(ValueError):
        sources.parse_quakes({"type": "FeatureCollection"})


def test_전부_못_읽으면_멈춘다():
    """스키마가 통째로 바뀐 경우.

    조용히 빈 목록을 돌려주면 **지진이 없는 날과 구분되지 않는다.**
    빈 지도가 도는 영상이 그대로 올라가는 것이 제일 나쁘다.
    """
    broken = {"type": "FeatureCollection",
              "features": [{"attributes": {"magnitude": 5.0}} for _ in range(30)]}
    with pytest.raises(ValueError):
        sources.parse_quakes(broken)


def test_깊이가_음수면_0으로(payload):
    """해수면 위 기준점 때문에 음수 깊이가 온다."""
    one = json.loads(json.dumps(payload["features"][0]))
    one["geometry"]["coordinates"][2] = -3.2
    quakes = sources.parse_quakes({"features": [one]})
    assert quakes[0].depth_km == 0.0


def test_캐시가_있으면_네트워크를_타지_않는다(monkeypatch):
    def 폭발(*args, **kwargs):
        raise AssertionError("캐시가 있는데 네트워크를 탔다")

    monkeypatch.setattr(sources, "fetch_json", 폭발)
    quakes = sources.load_quakes("day", cache=FIXTURE)
    assert len(quakes) > 100


def test_에너지는_규모에_지수로_붙는다(payload):
    """규모 6은 규모 4의 1,000배다. 이 값이 점 크기와 소리 크기의 근거다."""
    quakes = sources.parse_quakes(payload)
    a = next(q for q in quakes if q.mag >= 4.0)
    ratio = sources.Quake(a.id, a.time, 0, 0, 0, a.mag + 2, "").energy / a.energy
    assert 999 < ratio < 1001


def test_probe_가_픽스처를_통과시킨다(payload):
    """확인용 스크립트가 정상 응답을 정상이라고 말하는가.

    사람이 제일 먼저 돌리는 것이 이 스크립트다. 여기가 거짓 경보를 내면
    형식이 맞는데도 맞지 않다고 보고하게 된다.
    """
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "tools"))
    import probe

    assert probe.report(payload) == 0


def test_probe_가_깨진_응답을_잡는다():
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "tools"))
    import probe

    assert probe.report({"type": "FeatureCollection"}) != 0
    assert probe.report({"features": [{"attributes": {}} for _ in range(30)]}) != 0
