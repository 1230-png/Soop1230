"""지울 영상을 고르는 규칙. **지우는 것은 되돌릴 수 없으므로** 여기가 중요하다."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import purge_videos  # noqa: E402

VIDEOS = [
    {"id": "a", "title": "숏츠 1", "published": "2026-09-01T02:00:00Z"},
    {"id": "b", "title": "숏츠 2", "published": "2026-09-21T23:00:00Z"},
    {"id": "c", "title": "지구의 오늘 1편", "published": "2026-09-23T02:00:00Z"},
]


def test_before_가_없으면_전부():
    assert len(purge_videos.select(VIDEOS, None)) == 3


def test_before_는_그_날짜_전만_고른다():
    """새로 올린 것을 같이 지우는 사고를 막는 유일한 장치다."""
    picked = purge_videos.select(VIDEOS, "2026-09-22")
    assert [v["id"] for v in picked] == ["a", "b"]


def test_경계_날짜는_포함하지_않는다():
    picked = purge_videos.select(VIDEOS, "2026-09-21")
    assert [v["id"] for v in picked] == ["a"]


def test_원본을_건드리지_않는다():
    purge_videos.select(VIDEOS, "2026-09-22")
    assert len(VIDEOS) == 3


def test_하루_삭제_한도가_업로드_몫을_남긴다():
    """전부 삭제에 써 버리면 그날은 영상을 못 올린다.

    videos.insert 가 1,600 유닛이므로 그만큼은 남아 있어야 한다.
    """
    budget = (purge_videos.DAILY_QUOTA - purge_videos.RESERVE) // purge_videos.DELETE_COST
    assert budget > 0
    assert purge_videos.RESERVE >= 1600
    assert budget * purge_videos.DELETE_COST + purge_videos.RESERVE <= purge_videos.DAILY_QUOTA
