"""프레임마다 사건을 몇 개 소화할지 정하는 규칙.

한 줄짜리 계산이지만 여기가 틀리면 배열이 정렬되지 않은 채로 영상이 끝난다.
프레임당 개수를 실수로 들고 다니며 빚을 갚는 방식이 실제로 그렇게 실패했고,
그래서 누적 목표로 바꿨다. 이 검사는 그 성질 — **마지막 프레임의 목표가
정확히 전체 사건 수** — 를 못 박는다.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def targets(total_events: int, total_frames: int) -> list[int]:
    """build.render_section 안의 누적 목표와 같은 식."""
    return [round((k + 1) * total_events / total_frames)
            for k in range(total_frames)]


@pytest.mark.parametrize("events,frames", [
    (1, 1), (1, 90), (768, 90), (107918, 3000), (5, 3), (3, 5),
    (35294, 1710), (99, 100), (100, 99),
])
def test_마지막_프레임이_전부_소화한다(events, frames):
    assert targets(events, frames)[-1] == events


@pytest.mark.parametrize("events,frames", [
    (768, 90), (107918, 3000), (3, 5), (100, 99),
])
def test_목표는_줄지_않는다(events, frames):
    """되돌아가는 목표가 생기면 그 프레임은 사건을 하나도 못 먹는다."""
    seq = targets(events, frames)
    assert all(b >= a for a, b in zip(seq, seq[1:]))


def test_사건보다_프레임이_많아도_된다():
    """기수 정렬처럼 사건이 적은 꼭지. 한 프레임에 한 개도 안 먹는 구간이
    생기는 것은 정상이고, 그래도 총합은 맞아야 한다."""
    seq = targets(10, 100)
    assert seq[-1] == 10
    assert seq[0] == 0
