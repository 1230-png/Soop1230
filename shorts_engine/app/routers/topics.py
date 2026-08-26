"""주제 진단 라우터.

"왜 아무것도 제외되지 않는가"를 확인하는 용도다. 채널 초기에는 표본이
모자라 제외 목록이 비어 있는 게 정상인데, 그걸 버그로 오해하기 쉽다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.schemas import FailingTopicOut, TopicCoverageOut
from app.services.feedback import get_failing_topics, get_topic_coverage

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("/failing", response_model=list[FailingTopicOut])
async def failing_topics(
    session: AsyncSession = Depends(get_session),
) -> list[FailingTopicOut]:
    """현재 프롬프트에서 배제되는 주제."""
    return [FailingTopicOut(**t.__dict__) for t in await get_failing_topics(session)]


@router.get("/coverage", response_model=list[TopicCoverageOut])
async def topic_coverage(
    session: AsyncSession = Depends(get_session),
) -> list[TopicCoverageOut]:
    """카테고리별 표본 현황.

    enough_data가 False면 그 카테고리는 성적이 아무리 나빠도 제외되지 않는다.
    """
    return [TopicCoverageOut(**row) for row in await get_topic_coverage(session)]


@router.get("/thresholds")
async def thresholds() -> dict:
    """현재 판정 기준. 환경변수로 조정할 수 있다."""
    s = get_settings()
    return {
        "min_views": s.feedback_min_views,
        "like_ratio_threshold": s.feedback_like_ratio_threshold,
        "min_samples": s.feedback_min_samples,
        "설명": (
            f"조회수 {s.feedback_min_views} 이상인 영상이 카테고리당 "
            f"{s.feedback_min_samples}편 이상 쌓였을 때, 그 평균 좋아요 비율이 "
            f"{s.feedback_like_ratio_threshold * 100:.1f}% 미만이면 제외한다."
        ),
    }
