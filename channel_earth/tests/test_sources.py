"""응답 파싱. **네트워크를 타지 않는다** — 픽스처만 읽는다.

2026-09-27 에 GitHub Actions 에서 **실제 응답으로 확인했다**
(run 36297009327). `all_day` 175건이 **한 줄도 버려지지 않고** 읽혔고
규모 범위는 0.0~5.6 이었다. 즉 `features[].properties.mag` · `.time` ·
`.place` 와 `geometry.coordinates` 가 우리가 보고 쓴 그대로다.

이 검사는 그래서 "맞는지 확인"이 아니라 **"틀어지면 알아차리는"** 쪽이다.
피드 형식은 우리가 고칠 수 없는 남의 것이고 언제든 바뀔 수 있다.
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


class TestCoordinateRange:
    """좌표가 지구 위에 있는지.

    GeoJSON 은 `[경도, 위도]` 순서이고 USGS 도 그렇다(2026-09-27 실제 응답
    175건이 전부 그 순서로 읽혔다). 하지만 만약 어느 날 뒤바뀌면
    **파싱은 전부 성공하고 점만 엉뚱한 곳에 찍힌다** — 지도가 조용히
    거짓말을 하고, 지진 정보를 사실처럼 내보내는 것이 이 채널에서 가장
    나쁜 실패다. 위도가 ±90 을 넘는 줄이 쏟아지면 그때 알 수 있다.
    """

    def feature(self, lon, lat, mag=5.0):
        return {"type": "Feature",
                "properties": {"mag": mag, "time": 1_790_000_000_000,
                               "place": "somewhere"},
                "geometry": {"type": "Point", "coordinates": [lon, lat, 10.0]}}

    def test_지구_밖_좌표는_버린다(self):
        payload = {"features": [self.feature(139.7, 35.6),
                                self.feature(35.6, 139.7)]}
        quakes = sources.parse_quakes(payload)
        assert len(quakes) == 1
        assert quakes[0].lat == 35.6 and quakes[0].lon == 139.7

    def test_경계값은_받는다(self):
        payload = {"features": [self.feature(180.0, 90.0),
                                self.feature(-180.0, -90.0)]}
        assert len(sources.parse_quakes(payload)) == 2

    def test_순서가_바뀌면_전부_버려지고_멈춘다(self):
        # 경도·위도가 통째로 뒤바뀌면 대부분이 범위를 벗어난다. 그때는
        # 빈 목록을 돌려주지 않고 예외를 낸다 — 조용히 빈 영상이 나오는
        # 것이 제일 나쁘다.
        swapped = {"features": [self.feature(45.0, 175.0),
                                self.feature(-30.0, 160.0)]}
        with pytest.raises(ValueError):
            sources.parse_quakes(swapped)

    def test_버린_건수를_알린다(self, capsys):
        payload = {"features": [self.feature(139.7, 35.6),
                                self.feature(35.6, 139.7)]}
        sources.parse_quakes(payload)
        assert "좌표가 지구 밖" in capsys.readouterr().err
