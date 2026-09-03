"""FastAPI 진입점.

로컬 PC에서 뜬다. Ollama가 로컬 전용이라 생성부는 여기서만 돌 수 있고,
결과는 Postgres 큐에 쌓여 GitHub Actions가 꺼내 쓴다.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.routers import metrics, scripts, topics

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 기동 시 DB 연결을 확인한다. 잘못된 접속 문자열을 첫 요청까지 끌고 가지 않는다.
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("DB 연결 확인")
    except Exception as exc:  # noqa: BLE001
        logger.error("DB에 연결하지 못했습니다: %s", exc)
        raise
    yield
    await engine.dispose()


app = FastAPI(
    title="Shorts Engine",
    description=(
        "피드백 루프 기반 쇼츠 파이프라인. "
        "실적이 나쁜 주제를 프롬프트에서 배제하고, 나레이션 길이에 맞춰 영상을 만든다."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(scripts.router)
app.include_router(metrics.router)
app.include_router(topics.router)


@app.get("/health")
async def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "ollama_host": s.ollama_host,
        "ollama_model": s.ollama_model,
    }
