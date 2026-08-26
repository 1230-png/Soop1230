"""ORM 모델.

설계 판단 네 가지:

1. 지표는 append-only 시계열이다. 한 행을 UPDATE 하면 성장 곡선을 잃고,
   실패한 수집이 멀쩡한 값을 덮어쓴다. 스냅샷을 쌓고 최신값은 뷰로 뽑는다.
2. like_ratio는 DB 생성 컬럼이다. 파이썬에서 계산하면 라우터와 분석 쿼리가
   서로 다른 공식을 쓰게 되는 날이 온다.
3. NULLIF(view_count, 0) — 조회수 0인 신규 영상에서 0 나눗셈이 나면
   수집 잡 전체가 죽는다.
4. scripts.content_hash UNIQUE — 로컬 LLM은 같은 대본을 반복해서 낸다. DB에서 막는다.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ScriptStatus(str, enum.Enum):
    PENDING = "pending"
    RENDERING = "rendering"
    RENDERED = "rendered"
    UPLOADED = "uploaded"
    FAILED = "failed"


class TopicCategory(Base):
    """실패 판정의 단위. 대본 하나하나가 아니라 주제 묶음으로 판단한다."""

    __tablename__ = "topic_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label_ko: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    scripts: Mapped[list[Script]] = relationship(back_populates="topic_category")


class Script(Base):
    """Ollama가 만든 대본. 동시에 렌더링 대기 큐이기도 하다."""

    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    topic_category_id: Mapped[int] = mapped_column(
        ForeignKey("topic_categories.id"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[list] = mapped_column(JSONB, nullable=False)
    cta_question: Mapped[str] = mapped_column(Text, nullable=False)
    image_query: Mapped[str] = mapped_column(Text, nullable=False)

    # 재현과 사후 추적용. 어떤 주제를 제외한 프롬프트였는지 남겨야
    # 나중에 "이 대본은 왜 이렇게 나왔나"를 확인할 수 있다.
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    excluded_topics: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=ScriptStatus.PENDING.value
    )
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[str | None] = mapped_column(String(128))

    topic_category: Mapped[TopicCategory] = relationship(back_populates="scripts")
    video: Mapped[Video | None] = relationship(back_populates="script", uselist=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','rendering','rendered','uploaded','failed')",
            name="ck_scripts_status",
        ),
        # 큐에서 꺼낼 때만 쓰는 인덱스라 부분 인덱스로 작게 유지한다.
        Index(
            "idx_scripts_pending",
            "created_at",
            postgresql_where="status = 'pending'",
        ),
    )


class Video(Base):
    """업로드가 끝난 영상. 대본 하나당 하나."""

    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    script_id: Mapped[int] = mapped_column(
        ForeignKey("scripts.id"), unique=True, nullable=False
    )
    youtube_video_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False
    )
    # 대본의 카테고리를 여기에 복제해 둔다. 분석 쿼리가 scripts를 거치지 않아도 되고,
    # 대본의 카테고리가 나중에 바뀌어도 발행 시점의 사실이 보존된다.
    topic_category_id: Mapped[int] = mapped_column(
        ForeignKey("topic_categories.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    duration_sec: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    script: Mapped[Script] = relationship(back_populates="video")
    metrics: Mapped[list[VideoMetric]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )


class VideoMetric(Base):
    """지표 스냅샷. 갱신하지 않고 계속 쌓는다."""

    __tablename__ = "video_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    view_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    like_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    comment_count: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Analytics API에서만 나온다. Data API만 쓰는 수집에서는 NULL로 남는다.
    avg_view_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # 계산을 DB 한 곳에 둔다. 조회수 0이면 NULL이 되어 집계에서 자동으로 빠진다.
    like_ratio: Mapped[float | None] = mapped_column(
        Numeric(6, 5),
        Computed("like_count::numeric / NULLIF(view_count, 0)", persisted=True),
    )

    video: Mapped[Video] = relationship(back_populates="metrics")

    __table_args__ = (
        UniqueConstraint("video_id", "fetched_at", name="uq_metric_snapshot"),
        # v_latest_metrics의 DISTINCT ON (video_id) ORDER BY fetched_at DESC 를
        # 인덱스만으로 처리하려면 정렬 방향이 쿼리와 같아야 한다.
        Index("idx_metrics_latest", "video_id", desc("fetched_at")),
        CheckConstraint("view_count >= 0", name="ck_metrics_views_nonneg"),
        CheckConstraint("like_count >= 0", name="ck_metrics_likes_nonneg"),
    )
