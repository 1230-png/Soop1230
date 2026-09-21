"""좌표 변환과 색·소리 매핑. 렌더 자체는 눈으로 보지만, 매핑은 숫자로 못 박는다."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib import audio, render  # noqa: E402

SHORT = render.Layout.for_size(1080, 1920)
LONG = render.Layout.for_size(1920, 1080)


@pytest.mark.parametrize("layout", [SHORT, LONG])
def test_경도_0이_지도_가운데(layout):
    x, _ = layout.project(0.0, 0.0)
    assert x == pytest.approx(layout.map_x + layout.map_w / 2)


@pytest.mark.parametrize("layout", [SHORT, LONG])
def test_경도_양끝이_지도_양끝(layout):
    left, _ = layout.project(-180.0, 0.0)
    right, _ = layout.project(180.0, 0.0)
    assert left == pytest.approx(layout.map_x)
    assert right == pytest.approx(layout.map_x + layout.map_w)


@pytest.mark.parametrize("layout", [SHORT, LONG])
def test_위도가_클수록_위쪽(layout):
    """화면 좌표는 아래로 갈수록 커진다. 한 번 뒤집으면 지도가 상하 반전된다."""
    _, north = layout.project(0.0, 60.0)
    _, south = layout.project(0.0, -60.0)
    assert north < south


def test_잘라_낸_위도_밖은_알려_준다():
    """남극은 지도에서 잘라 냈다. 그 위도의 지진은 그리지 않는다."""
    assert SHORT.on_map(0.0)
    assert SHORT.on_map(79.0)
    assert not SHORT.on_map(-80.0)
    assert not SHORT.on_map(85.0)


def test_세로는_세로로_가로는_가로로():
    assert SHORT.vertical and not LONG.vertical


def test_깊을수록_파랗고_얕을수록_붉다():
    """USGS 관례다. 얕은 지진이 같은 규모라도 지표에 크게 온다."""
    shallow = render.depth_color(0.0)
    deep = render.depth_color(600.0)
    assert shallow[0] > shallow[2], "얕은 쪽은 빨강이 파랑보다 세야 한다"
    assert deep[2] > deep[0], "깊은 쪽은 파랑이 빨강보다 세야 한다"


def test_깊이_색은_구간_밖에서도_돌려준다():
    assert render.depth_color(-5.0) == render.DEPTH_STOPS[0][1]
    assert render.depth_color(5000.0) == render.DEPTH_STOPS[-1][1]


def test_얕을수록_높은_음():
    assert audio.pitch_for_depth(0.0) > audio.pitch_for_depth(600.0)


def test_클수록_큰_소리():
    levels = [audio.level_for_magnitude(m) for m in (1.0, 3.0, 5.0, 7.0)]
    assert levels == sorted(levels)
    assert all(0.0 < v <= 0.95 for v in levels)


def test_정규화는_피크를_맞춘다():
    import numpy as np
    quiet = np.sin(np.linspace(0, 100, 4410)) * 0.001
    pcm = audio.to_pcm16(quiet, peak=0.8)
    peak = max(abs(int.from_bytes(pcm[i:i + 2], "little", signed=True))
               for i in range(0, len(pcm), 2))
    assert peak == pytest.approx(0.8 * 32767, rel=0.02)
