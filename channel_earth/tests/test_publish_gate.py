"""가짜 데이터가 발행되지 않는지. 이 저장소에서 가장 중요한 검사다.

지진 정보를 사실처럼 내보내는 것은 그 자체로 해가 된다. 렌더 확인용
픽스처로 만든 영상이 실수로 올라가는 경로를 여기서 막는다.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build as builder  # noqa: E402


def 정상() -> dict:
    return {"title": "지구의 오늘 — 09월 21일 지진 290건",
            "description": "설명", "quake_count": 290,
            "duration_seconds": 52.0, "synthetic": False}


def test_정상이면_통과한다():
    builder.verify_publishable(정상())


def test_가짜_데이터는_막는다():
    meta = 정상() | {"synthetic": True}
    with pytest.raises(SystemExit) as caught:
        builder.verify_publishable(meta)
    assert "가짜" in str(caught.value)


def test_건수가_너무_적으면_막는다():
    """피드가 비었거나 파싱이 통째로 실패했을 때 여기서 걸린다."""
    with pytest.raises(SystemExit):
        builder.verify_publishable(정상() | {"quake_count": 3})


def test_렌더가_끊기면_막는다():
    with pytest.raises(SystemExit):
        builder.verify_publishable(정상() | {"duration_seconds": 4.0})


@pytest.mark.parametrize("field", ["title", "description"])
def test_제목이나_설명이_비면_막는다(field):
    with pytest.raises(SystemExit):
        builder.verify_publishable(정상() | {field: "   "})


def test_시간대_막대는_전부_센다():
    """한 건이라도 빠지면 막대 합과 누적 건수가 어긋난다."""
    import datetime as dt
    from lib.sources import Quake
    start = dt.datetime(2026, 9, 21, tzinfo=dt.timezone.utc)
    quakes = [Quake(str(i), start + dt.timedelta(minutes=17 * i), 0, 0, 10,
                    4.0, "") for i in range(80)]
    counts = builder.hour_counts(quakes, start, 24)
    assert sum(counts) == len(quakes)
    assert len(counts) == 24


def test_점_크기는_규모에_따라_커진다():
    sizes = [builder.dot_radius(m, 1.0) for m in (1, 3, 5, 7)]
    assert sizes == sorted(sizes)
