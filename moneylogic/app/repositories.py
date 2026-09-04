"""데이터베이스 접근 계층 (Repository Pattern).

VideoTask 캐싱 로직을 구현한다.
"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import VideoTask


class VideoTaskRepository:
    """VideoTask 데이터베이스 작업"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_ticker_and_date(self, ticker: str, target_date: str) -> VideoTask | None:
        """같은 ticker와 date의 기존 작업 조회 (캐싱).

        Args:
            ticker: 종목 코드
            target_date: 날짜 (YYYY-MM-DD)

        Returns:
            기존 작업이 있으면 반환, 없으면 None
        """
        result = await self.session.execute(
            select(VideoTask)
            .where(VideoTask.ticker == ticker)
            .where(VideoTask.target_date == target_date)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        ticker: str,
        target_date: str,
        topic: str = None,
        script_content: str = None,
    ) -> VideoTask:
        """새로운 작업 생성.

        Args:
            ticker: 종목 코드
            target_date: 날짜 (YYYY-MM-DD)
            topic: 영상 주제
            script_content: 스크립트 (JSON)

        Returns:
            생성된 VideoTask
        """
        task = VideoTask(
            ticker=ticker,
            target_date=target_date,
            topic=topic,
            script_content=script_content,
            is_rendered=False,
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def update_audio_path(self, task_id: int, audio_path: str) -> VideoTask:
        """오디오 경로 업데이트."""
        task = await self.session.get(VideoTask, task_id)
        if task:
            task.audio_path = audio_path
            task.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(task)
        return task

    async def mark_rendered(self, task_id: int, video_path: str) -> VideoTask:
        """렌더링 완료 표시."""
        task = await self.session.get(VideoTask, task_id)
        if task:
            task.is_rendered = True
            task.video_path = video_path
            task.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(task)
        return task

    async def get_by_id(self, task_id: int) -> VideoTask | None:
        """ID로 작업 조회."""
        return await self.session.get(VideoTask, task_id)
