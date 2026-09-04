"""데이터베이스 연결 및 세션 관리.

SQLAlchemy async 엔진과 세션 팩토리를 설정한다.
"""

import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# 환경 변수에서 DB URL 읽기
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL 환경 변수가 설정되지 않았습니다.")

# postgresql:// → postgresql+asyncpg:// 변환 (async 지원)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# 비동기 엔진 생성
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # SQL 로깅 비활성화 (프로덕션에서는 False)
    pool_size=5,
    max_overflow=10,
)

# 비동기 세션 팩토리
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """FastAPI dependency: 요청마다 새로운 DB 세션 제공"""
    async with AsyncSessionLocal() as session:
        yield session
