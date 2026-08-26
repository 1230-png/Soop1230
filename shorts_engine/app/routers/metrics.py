"""지표 수집 라우터.

수집은 UPDATE가 아니라 INSERT다. 스냅샷을 쌓아야 성장 곡선을 볼 수 있고,
실패한 수집이 멀쩡한 값을 덮어쓰지 않는다.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Video, VideoMetric
from app.schemas import MetricsSyncResponse
from app.services import youtube

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.post("/sync", response_model=MetricsSyncResponse)
async def sync_metrics(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(
        default=200,
        ge=1,
        le=1000,
        description="한 번에 조회할 영상 수. Data API 할당량을 고려해 제한한다.",
    ),
) -> MetricsSyncResponse:
    """업로드된 영상의 지표를 가져와 스냅샷으로 저장한다.

    Data API의 videos.list는 호출당 1 unit이고 50개씩 묶이므로
    영상 200개를 훑어도 4 units밖에 들지 않는다. 업로드(1600 units)에 비하면
    무시할 만한 비용이라 자주 돌려도 된다.
    """
    videos = list(
        await session.scalars(
            select(Video).order_by(Video.published_at.desc()).limit(limit)
        )
    )
    if not videos:
        return MetricsSyncResponse(synced=0, skipped=0, analytics_available=False)

    by_yt_id = {v.youtube_video_id: v for v in videos}

    try:
        stats, analytics_ok = youtube.fetch_all(list(by_yt_id))
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    synced = 0
    for yt_id, stat in stats.items():
        video = by_yt_id.get(yt_id)
        if video is None:
            continue
        session.add(
            VideoMetric(
                video_id=video.id,
                view_count=stat.view_count,
                like_count=stat.like_count,
                comment_count=stat.comment_count,
                avg_view_pct=stat.avg_view_pct,
            )
        )
        synced += 1

    await session.commit()

    skipped = len(by_yt_id) - synced
    if skipped:
        logger.info("지표를 받지 못한 영상 %d개 (삭제·비공개 가능성)", skipped)

    return MetricsSyncResponse(
        synced=synced, skipped=skipped, analytics_available=analytics_ok
    )
