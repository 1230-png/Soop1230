"""FastAPI 메인 애플리케이션.

완전 자동화된 영상 생성 파이프라인:
1. 금융 데이터 크롤링 (yfinance)
2. LLM 스크립트 생성 (OpenAI)
3. TTS 음성 합성 (edge-tts / ElevenLabs)
4. 영상 렌더링 (moviepy)
5. YouTube 업로드 (비공개)
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import engine, get_session, AsyncSessionLocal
from app.models import Base, VideoTask
from app.repositories import VideoTaskRepository
from app.services.script_generator import generate_complete_script
from app.services.tts import synthesize_timeline
from app.services.video_renderer import render_video
from app.services.youtube_uploader import upload_video

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# FastAPI 앱 생성
app = FastAPI(
    title="MoneyLogic Video Generator",
    description="완전 자동화된 재무 영상 생성 파이프라인",
    version="1.0.0",
)

OUTPUT_DIR = Path(settings.output_dir)


@app.on_event("startup")
async def startup_event():
    """앱 시작 시 DB 테이블 생성."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ 데이터베이스 초기화 완료")


@app.get("/health")
async def health_check():
    """헬스 체크."""
    return {
        "status": "ok",
        "environment": settings.environment,
        "output_dir": str(OUTPUT_DIR),
    }


@app.post("/generate")
async def generate_video(
    ticker: str,
    target_date: str = None,
    background_tasks: BackgroundTasks = None,
    session: AsyncSession = Depends(get_session),
):
    """영상 생성 요청.

    Args:
        ticker: 종목 코드 (예: AAPL)
        target_date: 날짜 (YYYY-MM-DD, 기본값: 오늘)
        background_tasks: FastAPI BackgroundTasks

    Returns:
        {
            "task_id": 1,
            "ticker": "AAPL",
            "status": "pending|rendering|completed|failed",
            "message": "처리 중..."
        }
    """
    # 기본값: 오늘 날짜
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")

    repo = VideoTaskRepository(session)

    # 1. 중복 체크 (캐싱)
    existing = await repo.find_by_ticker_and_date(ticker, target_date)
    if existing:
        if existing.is_rendered:
            return {
                "task_id": existing.id,
                "ticker": ticker,
                "target_date": target_date,
                "status": "completed",
                "message": f"이미 생성된 영상: {existing.video_path}",
                "video_url": f"https://www.youtube.com/watch?v={existing.video_path}",
            }
        else:
            return {
                "task_id": existing.id,
                "ticker": ticker,
                "target_date": target_date,
                "status": "processing",
                "message": "이미 처리 중입니다",
            }

    # 2. 새 작업 생성
    task = await repo.create(
        ticker=ticker,
        target_date=target_date,
    )

    logger.info(f"📝 새 작업 생성: {ticker} ({target_date}) - Task ID: {task.id}")

    # 3. 백그라운드 작업 등록
    if background_tasks:
        background_tasks.add_task(
            _process_video_generation,
            task_id=task.id,
            ticker=ticker,
            target_date=target_date,
        )

    return {
        "task_id": task.id,
        "ticker": ticker,
        "target_date": target_date,
        "status": "pending",
        "message": "영상 생성이 시작되었습니다",
    }


async def _process_video_generation(task_id: int, ticker: str, target_date: str):
    """백그라운드 영상 생성 프로세스.

    1. 스크립트 생성
    2. TTS 음성 합성
    3. 영상 렌더링
    4. YouTube 업로드
    """
    async with AsyncSessionLocal() as session:
        repo = VideoTaskRepository(session)
        task = await repo.get_by_id(task_id)

        if not task:
            logger.error(f"❌ 작업을 찾을 수 없습니다: {task_id}")
            return

        try:
            logger.info(f"🚀 작업 시작: {ticker} ({target_date})")

            # Step 1: 스크립트 생성
            logger.info(f"📝 스크립트 생성 중...")
            script_data = await generate_complete_script(ticker)
            topic = script_data.get("topic", f"{ticker} 분석")
            timeline = script_data.get("timeline", [])

            # DB에 저장
            task.topic = topic
            task.script_content = json.dumps(script_data, ensure_ascii=False)
            await session.commit()

            # Step 2: TTS 음성 합성
            logger.info(f"🎤 음성 합성 중...")
            audio_dir = OUTPUT_DIR / ticker / target_date
            audio_path, updated_timeline = await synthesize_timeline(timeline, audio_dir)

            # DB 업데이트
            await repo.update_audio_path(task_id, str(audio_path))

            # Step 3: 영상 렌더링
            logger.info(f"🎬 영상 렌더링 중...")
            video_path = audio_dir / f"{ticker}_{target_date}.mp4"
            await render_video(
                audio_path=audio_path,
                output_path=video_path,
                ticker=ticker,
                topic=topic,
                date_str=target_date,
                timeline=updated_timeline,
            )

            # DB 업데이트
            await repo.mark_rendered(task_id, str(video_path))

            # Step 4: YouTube 업로드
            logger.info(f"📤 YouTube 업로드 중...")
            youtube_video_id = await upload_video(
                video_path=video_path,
                title=f"[{ticker}] {topic}",
                description=f"머니로직 - 재무 분석\n{topic}\n\n방송일: {target_date}",
                tags=[ticker, "재무분석", "주식", "경제", "머니로직"],
                is_private=True,  # 비공개
            )

            logger.info(f"✅ 완료! {ticker} ({target_date})")
            logger.info(f"   영상: {video_path}")
            logger.info(f"   YouTube: https://www.youtube.com/watch?v={youtube_video_id}")

        except Exception as e:
            logger.error(f"❌ 오류 발생: {str(e)}", exc_info=True)
            # 실패 상태 저장 (선택사항)


@app.get("/task/{task_id}")
async def get_task_status(
    task_id: int,
    session: AsyncSession = Depends(get_session),
):
    """작업 상태 조회."""
    repo = VideoTaskRepository(session)
    task = await repo.get_by_id(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")

    return {
        "id": task.id,
        "ticker": task.ticker,
        "target_date": task.target_date,
        "topic": task.topic,
        "is_rendered": task.is_rendered,
        "video_path": task.video_path,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
