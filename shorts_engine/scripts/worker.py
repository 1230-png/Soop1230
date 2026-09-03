"""큐 소비 워커. GitHub Actions에서 돈다.

Postgres에서 대본을 하나 선점해 렌더링하고, 업로드는 호출부에 맡긴다.
Ollama가 필요 없으므로 PC가 꺼져 있어도 돈다 — 큐에 대본이 남아 있는 한.

    python3 scripts/worker.py --out-dir /tmp/out
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Script, ScriptStatus  # noqa: E402
from render.renderer import RenderRequest, render  # noqa: E402

# 훅 구간에서 쓸 배경음. 대본에 없으면 이 기본값을 쓴다.
DEFAULT_AMBIENCE = ["low_drone"]


async def claim(worker_name: str) -> Script | None:
    """FOR UPDATE SKIP LOCKED로 한 건 선점한다.

    이게 없으면 예약 실행과 수동 실행이 겹칠 때 두 워커가 같은 대본을
    렌더링해 같은 영상이 두 번 올라간다.
    """
    async with SessionLocal() as session:
        row = await session.execute(
            text(
                "SELECT id FROM scripts WHERE status = 'pending' "
                "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"
            )
        )
        script_id = row.scalar_one_or_none()
        if script_id is None:
            await session.commit()
            return None

        script = await session.get(Script, script_id)
        script.status = ScriptStatus.RENDERING.value
        script.claimed_by = worker_name
        script.claimed_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(script)
        session.expunge(script)
        return script


async def mark(script_id: int, status: ScriptStatus) -> None:
    async with SessionLocal() as session:
        script = await session.get(Script, script_id)
        if script is not None:
            script.status = status.value
            await session.commit()


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--worker",
        default=os.environ.get("GITHUB_RUN_ID", "local"),
        help="선점 주체 식별자",
    )
    args = parser.parse_args()

    script = await claim(args.worker)
    if script is None:
        print("[중단] 큐가 비었습니다. 로컬에서 /scripts/generate 를 돌려 채우세요.",
              file=sys.stderr)
        print(json.dumps({"skipped": True, "reason": "queue_empty"}, ensure_ascii=False))
        return 0

    out_dir = Path(args.out_dir)
    video_path = out_dir / f"script_{script.id}.mp4"

    print(f"[렌더] #{script.id} {script.title}", file=sys.stderr)
    try:
        result = render(
            RenderRequest(
                script_id=script.id,
                title=script.title,
                hook=script.hook,
                body=list(script.body),
                cta_question=script.cta_question,
                image_query=script.image_query,
                ambience=DEFAULT_AMBIENCE,
            ),
            out_path=video_path,
            work_dir=out_dir / f"work_{script.id}",
        )
    except Exception as exc:  # noqa: BLE001
        # 실패한 대본을 pending으로 되돌리지 않는다. 같은 이유로 계속 실패하면
        # 큐가 막힌다. 사람이 원인을 보고 판단해야 한다.
        await mark(script.id, ScriptStatus.FAILED)
        print(f"[실패] 렌더링 오류: {exc}", file=sys.stderr)
        return 1

    await mark(script.id, ScriptStatus.RENDERED)

    print(
        f"[완료] {result.duration_sec:.1f}초, 컷 {result.cut_count}개 "
        f"(훅 {result.hook_cut_count}개), 배경사진 {'사용' if result.used_photo else '없음'}",
        file=sys.stderr,
    )
    # 업로드 단계가 이어받을 정보. 업로드 후 /scripts/{id}/complete 를 호출해야 한다.
    print(json.dumps({
        "skipped": False,
        "script_id": script.id,
        "video_path": str(video_path),
        "title": script.title,
        "duration_sec": round(result.duration_sec, 2),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
