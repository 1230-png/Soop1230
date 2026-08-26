"""대본 생성과 큐 소비.

큐 선점(`/claim`)은 반드시 FOR UPDATE SKIP LOCKED로 잠근다.
그러지 않으면 예약 실행과 수동 실행이 겹칠 때 두 워커가 같은 대본을
렌더링해 같은 영상이 두 번 올라간다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import Script, ScriptStatus, TopicCategory, Video
from app.schemas import (
    ClaimRequest,
    CompleteRequest,
    GenerateRequest,
    GenerateResponse,
    ScriptOut,
)
from app.services import ollama
from app.services.feedback import get_failing_topics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scripts", tags=["scripts"])


async def _pick_topic(
    session: AsyncSession, slug: str | None, failing_slugs: set[str]
) -> TopicCategory:
    """생성할 카테고리를 고른다.

    지정이 없으면 실패 판정을 받지 않은 활성 카테고리 중 가장 오래 안 쓴 것을 고른다.
    (실패 주제를 프롬프트에서 배제하는 것과 별개로, 애초에 고르지도 않는다.)
    """
    if slug:
        row = await session.scalar(
            select(TopicCategory).where(TopicCategory.slug == slug)
        )
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"없는 카테고리: {slug}")
        return row

    candidates = await session.scalars(
        select(TopicCategory)
        .where(TopicCategory.is_active.is_(True))
        .order_by(TopicCategory.id)
    )
    usable = [c for c in candidates if c.slug not in failing_slugs]
    if not usable:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "사용 가능한 카테고리가 없습니다. 모든 활성 카테고리가 실패 판정을 받았거나 "
            "카테고리가 등록되지 않았습니다.",
        )
    # 가장 최근에 만든 대본이 오래된 카테고리부터 쓴다.
    counts = await session.execute(
        text(
            "SELECT topic_category_id, MAX(created_at) AS last_used "
            "FROM scripts GROUP BY topic_category_id"
        )
    )
    last_used = {r.topic_category_id: r.last_used for r in counts}
    usable.sort(key=lambda c: (last_used.get(c.id) is not None, last_used.get(c.id)))
    return usable[0]


@router.post("/generate", response_model=GenerateResponse)
async def generate_scripts(
    req: GenerateRequest, session: AsyncSession = Depends(get_session)
) -> GenerateResponse:
    """실패 주제를 프롬프트에서 배제하고 대본을 생성해 큐에 넣는다.

    데이터가 부족하면 배제 목록이 비어 있는 채로 진행된다. 채널 초기에는 정상이다.
    """
    failing = await get_failing_topics(session)
    failing_slugs = {t.slug for t in failing}
    topic = await _pick_topic(session, req.topic_slug, failing_slugs)

    created: list[Script] = []
    duplicates = 0
    excluded: list[str] = []

    for _ in range(req.count):
        try:
            generated, prompt, excluded = await ollama.generate_script(
                topic.label_ko, failing
            )
        except RuntimeError as exc:
            # Ollama가 안 떠 있거나 재시도를 모두 소진한 경우.
            # 이미 만든 것은 살리고 여기서 멈춘다.
            if created:
                logger.warning("일부만 생성하고 중단: %s", exc)
                break
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

        script = Script(
            topic_category_id=topic.id,
            title=generated.title,
            hook=generated.hook,
            body=generated.body,
            cta_question=generated.cta_question,
            image_query=generated.image_query,
            model=get_settings().ollama_model,
            prompt=prompt,
            excluded_topics=excluded,
            content_hash=generated.content_hash(),
        )
        session.add(script)
        try:
            # 중복은 UNIQUE 제약으로 걸린다. 한 건씩 flush해야
            # 중복 하나가 배치 전체를 롤백시키지 않는다.
            await session.flush()
            created.append(script)
        except IntegrityError:
            await session.rollback()
            duplicates += 1
            logger.info("중복 대본 건너뜀: %s", generated.title)

    await session.commit()
    return GenerateResponse(
        created=[ScriptOut.model_validate(s) for s in created],
        skipped_duplicates=duplicates,
        excluded_topics=excluded,
    )


@router.post("/claim", response_model=ScriptOut | None)
async def claim_script(
    req: ClaimRequest, session: AsyncSession = Depends(get_session)
) -> ScriptOut | None:
    """큐에서 대본 한 건을 선점한다. 비어 있으면 null."""
    # SKIP LOCKED가 핵심이다. 동시에 두 워커가 들어와도 서로 다른 행을 가져간다.
    row = await session.execute(
        text(
            """
            SELECT id FROM scripts
            WHERE status = 'pending'
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """
        )
    )
    script_id = row.scalar_one_or_none()
    if script_id is None:
        await session.commit()
        return None

    script = await session.get(Script, script_id)
    script.status = ScriptStatus.RENDERING.value
    script.claimed_by = req.worker
    # SQL 표현식이 아니라 파이썬 datetime을 넣어야 한다. text("now()")를 대입하면
    # asyncpg가 TextClause를 바인딩하지 못해 런타임에 터진다.
    script.claimed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(script)
    return ScriptOut.model_validate(script)


@router.post("/{script_id}/complete", response_model=ScriptOut)
async def complete_script(
    script_id: int,
    req: CompleteRequest,
    session: AsyncSession = Depends(get_session),
) -> ScriptOut:
    """업로드 완료를 기록한다."""
    script = await session.get(Script, script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"없는 대본: {script_id}")

    session.add(
        Video(
            script_id=script.id,
            youtube_video_id=req.youtube_video_id,
            topic_category_id=script.topic_category_id,
            title=script.title,
            duration_sec=req.duration_sec,
            published_at=req.published_at,
        )
    )
    script.status = ScriptStatus.UPLOADED.value
    try:
        await session.commit()
    except IntegrityError as exc:
        # 진짜 방어선은 videos.script_id / youtube_video_id 의 UNIQUE 제약이다.
        # status만 보고 판단하면 둘이 어긋났을 때 500이 그대로 나간다.
        # 업로드는 성공했는데 이 호출이 네트워크 문제로 실패해 재시도할 때 실제로 겪는다.
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"이미 기록된 업로드입니다 (대본 {script_id} "
            f"또는 영상 {req.youtube_video_id}). 재시도라면 무시해도 됩니다.",
        ) from exc

    await session.refresh(script)
    return ScriptOut.model_validate(script)


@router.post("/{script_id}/fail", response_model=ScriptOut)
async def fail_script(
    script_id: int, session: AsyncSession = Depends(get_session)
) -> ScriptOut:
    """렌더링/업로드 실패를 기록한다.

    실패한 대본을 pending으로 되돌리지 않는 이유: 같은 이유로 계속 실패하면
    큐가 막힌다. 사람이 원인을 보고 판단해야 한다.
    """
    script = await session.get(Script, script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"없는 대본: {script_id}")
    script.status = ScriptStatus.FAILED.value
    await session.commit()
    await session.refresh(script)
    return ScriptOut.model_validate(script)
