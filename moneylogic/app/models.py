"""SQLAlchemy 데이터베이스 모델.

VideoTask: 캐싱 테이블 (같은 ticker/date 중복 방지)
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class VideoTask(Base):
    """영상 생성 작업 캐싱 테이블.

    같은 ticker와 target_date로 요청이 들어오면 이미 생성된 데이터를 재사용한다.
    이를 통해 OpenAI API 요금을 절감한다.
    """
    __tablename__ = "video_tasks"

    # 필수 필드
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    target_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD 형식

    # 콘텐츠 필드
    topic = Column(String(255), nullable=True)  # "애플 서비스 매출 구조"
    script_content = Column(Text, nullable=True)  # JSON 또는 마크다운 형식
    audio_path = Column(String(500), nullable=True)  # /tmp/audio_20240905.mp3

    # 상태 필드
    is_rendered = Column(Boolean, default=False, nullable=False)
    video_path = Column(String(500), nullable=True)  # /tmp/video_20240905.mp4

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 복합 인덱스: ticker + target_date는 고유해야 한다 (중복 방지)
    __table_args__ = (
        UniqueConstraint('ticker', 'target_date', name='uq_ticker_date'),
    )

    def __repr__(self):
        return f"<VideoTask(id={self.id}, ticker={self.ticker}, date={self.target_date}, rendered={self.is_rendered})>"
