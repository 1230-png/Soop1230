"""API 입출력 스키마."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerateRequest(BaseModel):
    topic_slug: str | None = Field(
        default=None,
        description="비우면 실패 판정을 받지 않은 활성 카테고리 중에서 자동으로 고른다",
    )
    count: int = Field(default=1, ge=1, le=20, description="한 번에 생성할 대본 수")


class ScriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_category_id: int
    title: str
    hook: str
    body: list[str]
    cta_question: str
    image_query: str
    status: str
    excluded_topics: list[str]
    created_at: datetime


class GenerateResponse(BaseModel):
    created: list[ScriptOut]
    skipped_duplicates: int = Field(
        description="이미 같은 내용이 있어 저장하지 않은 수"
    )
    excluded_topics: list[str] = Field(
        description="이번 생성에서 프롬프트로 배제한 주제. 비어 있으면 판정 데이터가 부족한 것"
    )


class ClaimRequest(BaseModel):
    worker: str = Field(
        max_length=128, description="선점 주체 식별자 (예: github-actions-run-123)"
    )


class CompleteRequest(BaseModel):
    youtube_video_id: str = Field(min_length=5, max_length=32)
    duration_sec: float = Field(gt=0)
    published_at: datetime


class FailingTopicOut(BaseModel):
    slug: str
    label_ko: str
    sample_size: int
    avg_like_ratio: float
    avg_view_pct: float | None


class TopicCoverageOut(BaseModel):
    slug: str
    label_ko: str
    qualified_samples: int
    total_videos: int
    avg_like_ratio: float | None
    enough_data: bool


class MetricsSyncResponse(BaseModel):
    synced: int
    skipped: int
    analytics_available: bool = Field(
        description="False면 시청 지속률이 NULL로 저장된다 (Analytics 스코프 없음)"
    )
