"""실제 PostgreSQL을 상대로 도는 API 테스트.

DATABASE_URL이 없으면 건너뛴다. 여기서만 잡히는 것들이 있다 —
생성 컬럼의 0 나눗셈, SKIP LOCKED 동시성, UNIQUE 제약 위반의 응답 코드.
"""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql+asyncpg"),
    reason="실제 PostgreSQL 필요 (DATABASE_URL 환경변수)",
)


@pytest.fixture
def fake_script():
    from app.services.ollama import GeneratedScript

    return GeneratedScript(
        title="테스트 대본 " + datetime.now().strftime("%H%M%S%f"),
        hook="완전한 어둠에서도 뭔가 아른거린 적 있나요?",
        body=["눈을 감아도 희미한 점이 떠다닙니다.",
              "포스펜이라 부르며 시신경이 스스로 내는 신호입니다."],
        cta_question="여러분도 본 적 있나요?",
        image_query="total darkness abstract",
    )


@pytest.fixture
async def client():
    import httpx
    from httpx import ASGITransport

    from app.main import app

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as c:
            yield c


@pytest.mark.asyncio
async def test_완료_재시도는_500이_아니라_409(client, fake_script):
    """업로드는 성공했는데 complete 호출이 네트워크 문제로 실패해 재시도하는 경우.

    status만 검사하면 videos.script_id UNIQUE 제약에 걸려 500이 그대로 나간다.
    """
    with patch("app.routers.scripts.ollama.generate_script",
               new=AsyncMock(return_value=(fake_script, "p", []))):
        await client.post("/scripts/generate", json={"count": 1})

    claimed = (await client.post("/scripts/claim", json={"worker": "t"})).json()
    assert claimed is not None

    payload = {
        "youtube_video_id": "RETRY" + datetime.now().strftime("%H%M%S%f")[:8],
        "duration_sec": 38.4,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    assert (await client.post(f"/scripts/{claimed['id']}/complete", json=payload)).status_code == 200

    retry = await client.post(f"/scripts/{claimed['id']}/complete", json=payload)
    assert retry.status_code == 409, f"재시도가 {retry.status_code}로 떨어짐"
    assert "이미 기록된" in retry.json()["detail"]


@pytest.mark.asyncio
async def test_조회수0_영상은_판정에서_빠진다(client):
    """like_ratio 생성 컬럼이 NULLIF로 0 나눗셈을 막는지."""
    from sqlalchemy import text

    from app.db import SessionLocal

    async with SessionLocal() as s:
        vid = await s.scalar(text("SELECT id FROM videos LIMIT 1"))
        if vid is None:
            pytest.skip("videos 행 없음")
        await s.execute(
            text("INSERT INTO video_metrics (video_id,view_count,like_count,comment_count)"
                 " VALUES (:v,0,0,0)"), {"v": vid})
        await s.commit()
        ratio = await s.scalar(
            text("SELECT like_ratio FROM video_metrics WHERE video_id=:v"
                 " ORDER BY fetched_at DESC LIMIT 1"), {"v": vid})
        assert ratio is None, "조회수 0인데 like_ratio가 NULL이 아니다"


@pytest.mark.asyncio
async def test_동시_선점은_서로_다른_대본을_가져간다(client):
    """SKIP LOCKED가 없으면 두 워커가 같은 대본을 렌더해 중복 업로드가 난다."""
    import asyncio

    from sqlalchemy import text

    from app.db import SessionLocal

    async with SessionLocal() as s:
        await s.execute(text("UPDATE scripts SET status='pending' WHERE status='rendering'"))
        await s.commit()

    results = await asyncio.gather(*[
        client.post("/scripts/claim", json={"worker": f"w{i}"}) for i in range(5)
    ])
    ids = [r.json()["id"] for r in results if r.status_code == 200 and r.json()]
    assert len(ids) == len(set(ids)), f"중복 선점 발생: {ids}"
