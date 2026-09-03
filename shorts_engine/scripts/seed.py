"""카테고리 등록 + 기존 콘텐츠 60편을 큐에 적재한다.

Ollama가 아직 한 편도 만들지 않았을 때도 발행이 이어지게 하고, 동시에
LLM 산출물과 성적을 비교할 기준선을 만든다.

    python3 scripts/seed.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Script, TopicCategory  # noqa: E402

LEGACY_CONTENT = (
    Path(__file__).resolve().parent.parent.parent
    / "channel_food" / "scripts" / "weird_content.json"
)

# 기존 JSON의 type 값과 대응한다.
CATEGORIES = {
    "perception": "지각 현상",
    "mandela": "만델라 효과",
    "unexplained": "미해결 현상",
    "urban_legend": "도시전설",
}


def _hash(title: str, hook: str, body: list[str]) -> str:
    payload = json.dumps(
        {"title": title, "hook": hook, "body": body}, ensure_ascii=False, sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def main() -> int:
    if not LEGACY_CONTENT.exists():
        print(f"[실패] 콘텐츠 파일이 없습니다: {LEGACY_CONTENT}", file=sys.stderr)
        return 1

    items = json.loads(LEGACY_CONTENT.read_text(encoding="utf-8"))

    async with SessionLocal() as session:
        # 카테고리
        existing = {c.slug: c for c in await session.scalars(select(TopicCategory))}
        for slug, label in CATEGORIES.items():
            if slug not in existing:
                cat = TopicCategory(slug=slug, label_ko=label)
                session.add(cat)
                existing[slug] = cat
        await session.flush()
        print(f"카테고리 {len(existing)}개 확인")

        inserted = duplicates = 0
        for item in items:
            slug = item.get("type", "perception")
            if slug not in existing:
                print(f"  [건너뜀] 알 수 없는 카테고리 '{slug}' (#{item['id']})")
                continue

            body = list(item["body"])
            # 기존 콘텐츠에는 댓글 유도 질문이 없다. twist를 질문형으로 쓴다.
            cta = item.get("twist", "여러분은 어떻게 생각하시나요?")

            script = Script(
                topic_category_id=existing[slug].id,
                title=item["title"],
                hook=item["hook"],
                body=body,
                cta_question=cta,
                image_query=item.get("image_query", "dark abstract"),
                model="seed:weird_content.json",
                prompt="(기존 콘텐츠 이관 — LLM 생성 아님)",
                excluded_topics=[],
                content_hash=_hash(item["title"], item["hook"], body),
            )
            session.add(script)
            try:
                await session.flush()
                inserted += 1
            except IntegrityError:
                await session.rollback()
                duplicates += 1

        await session.commit()

    print(f"대본 {inserted}편 적재, 중복 {duplicates}편 건너뜀")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
