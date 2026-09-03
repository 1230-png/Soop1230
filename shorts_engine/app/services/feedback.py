"""피드백 루프의 판정부.

"조회수 500 이상인데 좋아요 비율 1% 미만" 인 주제를 골라낸다.
단, 영상 단위가 아니라 **카테고리 단위 평균**으로 본다.

영상 하나로 판정하면 운 나쁜 한 편이 카테고리 전체를 영구히 배제한다.
쇼츠는 편차가 크므로 최소 표본을 요구하는 쪽이 안전하다.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings


@dataclass(frozen=True)
class FailingTopic:
    slug: str
    label_ko: str
    sample_size: int
    avg_like_ratio: float
    avg_view_pct: float | None


# v_latest_metrics를 쓰는 이유: video_metrics는 스냅샷이 계속 쌓이므로
# 그냥 조인하면 오래된 값까지 평균에 섞인다.
_FAILING_SQL = text(
    """
    SELECT tc.slug,
           tc.label_ko,
           COUNT(*)                AS sample_size,
           AVG(m.like_ratio)       AS avg_like_ratio,
           AVG(m.avg_view_pct)     AS avg_view_pct
    FROM v_latest_metrics m
    JOIN videos v           ON v.id = m.video_id
    JOIN topic_categories tc ON tc.id = v.topic_category_id
    WHERE m.view_count >= :min_views
      AND m.like_ratio IS NOT NULL      -- 조회수 0인 영상은 애초에 판정 대상이 아니다
    GROUP BY tc.slug, tc.label_ko
    HAVING COUNT(*) >= :min_samples
       AND AVG(m.like_ratio) < :ratio_threshold
    ORDER BY AVG(m.like_ratio) ASC
    """
)


async def get_failing_topics(session: AsyncSession) -> list[FailingTopic]:
    """제외해야 할 주제 목록.

    데이터가 부족하면 빈 목록을 돌려준다. 채널 초기에는 이게 정상이며,
    프롬프트에 제외 조건이 붙지 않는다.
    """
    s = get_settings()
    rows = await session.execute(
        _FAILING_SQL,
        {
            "min_views": s.feedback_min_views,
            "min_samples": s.feedback_min_samples,
            "ratio_threshold": s.feedback_like_ratio_threshold,
        },
    )
    return [
        FailingTopic(
            slug=r.slug,
            label_ko=r.label_ko,
            sample_size=r.sample_size,
            avg_like_ratio=float(r.avg_like_ratio),
            avg_view_pct=float(r.avg_view_pct) if r.avg_view_pct is not None else None,
        )
        for r in rows
    ]


_COVERAGE_SQL = text(
    """
    SELECT tc.slug,
           tc.label_ko,
           COUNT(m.video_id) FILTER (WHERE m.view_count >= :min_views) AS qualified,
           COUNT(m.video_id)                                           AS total,
           AVG(m.like_ratio) FILTER (WHERE m.view_count >= :min_views) AS avg_like_ratio
    FROM topic_categories tc
    LEFT JOIN videos v          ON v.topic_category_id = tc.id
    LEFT JOIN v_latest_metrics m ON m.video_id = v.id
    WHERE tc.is_active
    GROUP BY tc.slug, tc.label_ko
    ORDER BY tc.slug
    """
)


async def get_topic_coverage(session: AsyncSession) -> list[dict]:
    """카테고리별 표본 현황.

    "왜 아무것도 제외되지 않는가"를 설명하기 위한 진단용이다.
    판정에 쓰이는 qualified 수가 min_samples에 못 미치면 그 카테고리는
    아무리 성적이 나빠도 제외되지 않는다.
    """
    s = get_settings()
    rows = await session.execute(_COVERAGE_SQL, {"min_views": s.feedback_min_views})
    return [
        {
            "slug": r.slug,
            "label_ko": r.label_ko,
            "qualified_samples": r.qualified or 0,
            "total_videos": r.total or 0,
            "avg_like_ratio": float(r.avg_like_ratio)
            if r.avg_like_ratio is not None
            else None,
            "enough_data": (r.qualified or 0) >= s.feedback_min_samples,
        }
        for r in rows
    ]
