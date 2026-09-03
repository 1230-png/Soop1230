"""YouTube 지표 수집.

두 API를 쓴다. 둘 다 무료다.
  - Data API v3        조회수·좋아요·댓글 수
  - Analytics API      평균 시청 지속률 (averageViewPercentage)

Data API는 시청 지속률을 주지 않는다. 쇼츠 노출을 실제로 좌우하는 건 지속률이고
0~3초 빠른 컷도 그걸 겨냥한 조치이므로, 효과를 측정하려면 Analytics가 필요하다.

Analytics 스코프가 없으면 지속률만 NULL로 두고 나머지는 정상 수집한다.
스코프 하나 때문에 전체 수집이 죽으면 안 된다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings

logger = logging.getLogger(__name__)

DATA_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"

# videos.list는 한 번에 50개까지 받는다. 쪼개 부르면 할당량만 낭비된다.
_BATCH = 50


@dataclass(frozen=True)
class VideoStats:
    youtube_video_id: str
    view_count: int
    like_count: int
    comment_count: int
    avg_view_pct: float | None = None


def _credentials(scopes: list[str]) -> Credentials:
    s = get_settings()
    missing = [
        n
        for n, v in (
            ("YT_CLIENT_ID", s.yt_client_id),
            ("YT_CLIENT_SECRET", s.yt_client_secret),
            ("YT_REFRESH_TOKEN", s.yt_refresh_token),
        )
        if not v
    ]
    if missing:
        raise RuntimeError("자격증명이 없습니다: " + ", ".join(missing))

    creds = Credentials(
        token=None,
        refresh_token=s.yt_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=s.yt_client_id,
        client_secret=s.yt_client_secret,
        scopes=scopes,
    )
    creds.refresh(Request())
    return creds


def fetch_statistics(video_ids: list[str]) -> dict[str, VideoStats]:
    """Data API v3로 조회수·좋아요·댓글 수를 가져온다."""
    if not video_ids:
        return {}

    youtube = build("youtube", "v3", credentials=_credentials([DATA_SCOPE]))
    out: dict[str, VideoStats] = {}

    for i in range(0, len(video_ids), _BATCH):
        chunk = video_ids[i : i + _BATCH]
        resp = youtube.videos().list(part="statistics", id=",".join(chunk)).execute()
        for item in resp.get("items", []):
            st = item.get("statistics", {})
            out[item["id"]] = VideoStats(
                youtube_video_id=item["id"],
                # 좋아요를 숨긴 영상은 likeCount 키 자체가 없다. get 기본값 필수.
                view_count=int(st.get("viewCount", 0)),
                like_count=int(st.get("likeCount", 0)),
                comment_count=int(st.get("commentCount", 0)),
            )

    missing = set(video_ids) - set(out)
    if missing:
        # 삭제됐거나 비공개로 바뀐 영상. 수집을 멈출 이유는 아니다.
        logger.warning("통계를 받지 못한 영상 %d개: %s", len(missing), sorted(missing)[:5])
    return out


def fetch_retention(video_ids: list[str], lookback_days: int = 90) -> dict[str, float]:
    """Analytics API로 평균 시청 지속률(%)을 가져온다.

    스코프가 없거나 권한이 없으면 빈 dict를 돌려준다 — 지속률만 포기하고
    나머지 수집은 계속되어야 한다.
    """
    if not video_ids:
        return {}

    try:
        creds = _credentials([DATA_SCOPE, ANALYTICS_SCOPE])
        analytics = build("youtubeAnalytics", "v2", credentials=creds)
    except Exception as exc:  # noqa: BLE001 - 어떤 인증 실패든 지속률만 건너뛴다
        logger.warning("Analytics API를 쓸 수 없어 지속률을 건너뜁니다: %s", exc)
        return {}

    end = date.today()
    start = end - timedelta(days=lookback_days)
    out: dict[str, float] = {}

    for i in range(0, len(video_ids), _BATCH):
        chunk = video_ids[i : i + _BATCH]
        try:
            resp = (
                analytics.reports()
                .query(
                    ids="channel==MINE",
                    startDate=start.isoformat(),
                    endDate=end.isoformat(),
                    metrics="averageViewPercentage",
                    dimensions="video",
                    filters="video==" + ",".join(chunk),
                    maxResults=_BATCH,
                )
                .execute()
            )
        except HttpError as exc:
            logger.warning("Analytics 조회 실패, 지속률 없이 진행합니다: %s", exc)
            return out

        for row in resp.get("rows", []):
            # rows = [[video_id, averageViewPercentage], ...]
            if len(row) >= 2 and row[1] is not None:
                out[row[0]] = float(row[1])

    return out


def fetch_all(video_ids: list[str]) -> tuple[dict[str, VideoStats], bool]:
    """통계와 지속률을 합쳐서 돌려준다.

    Returns:
        (video_id -> VideoStats, Analytics 사용 가능 여부)
    """
    stats = fetch_statistics(video_ids)
    retention = fetch_retention(list(stats))

    if retention:
        stats = {
            vid: VideoStats(
                youtube_video_id=s.youtube_video_id,
                view_count=s.view_count,
                like_count=s.like_count,
                comment_count=s.comment_count,
                avg_view_pct=retention.get(vid),
            )
            for vid, s in stats.items()
        }

    return stats, bool(retention)
