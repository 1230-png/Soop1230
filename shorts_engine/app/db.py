"""비동기 DB 엔진과 세션.

무료 티어(Neon/Supabase)는 유휴 연결을 말없이 끊는다. pool_pre_ping으로
재사용 직전에 살아있는지 확인하지 않으면 하루에 한 번 도는 잡이
"connection was closed"로 실패한다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    echo=_settings.db_echo,
    pool_size=_settings.db_pool_size,
    pool_pre_ping=_settings.db_pool_pre_ping,
    # 무료 티어의 유휴 타임아웃보다 짧게 잡아 죽은 연결을 미리 버린다.
    pool_recycle=300,
)

SessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 의존성. 예외가 나면 롤백하고 항상 닫는다."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# 최신 지표만 뽑는 뷰. 마이그레이션에서 생성하고 쿼리에서 참조한다.
LATEST_METRICS_VIEW = """
CREATE OR REPLACE VIEW v_latest_metrics AS
SELECT DISTINCT ON (video_id)
       id, video_id, fetched_at, view_count, like_count,
       comment_count, avg_view_pct, like_ratio
FROM video_metrics
ORDER BY video_id, fetched_at DESC
"""
