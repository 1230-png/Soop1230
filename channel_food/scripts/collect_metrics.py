"""업로드한 영상의 조회수·좋아요를 받아 metrics.csv에 덧붙인다.

YouTube Data API v3의 videos.list(part=statistics)만 쓴다. 1회 1 unit이라
일일 할당량 10,000에 사실상 영향이 없다 (업로드 1편이 1,600 units).

  python3 collect_metrics.py            # 수집해서 metrics.csv에 추가
  python3 collect_metrics.py --dry-run  # 조회만 하고 파일은 건드리지 않는다

지표가 없어도 발행은 계속돼야 하므로, 실패해도 종료 코드는 0이다.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import feedback

ROOT = Path(__file__).resolve().parent.parent
USED_LOG = ROOT / "used_log.csv"
METRICS = ROOT / "metrics.csv"

# 업로드용 refresh token에 부여된 스코프와 정확히 같아야 한다. 더 좁은
# youtube.readonly를 요청하면 google-auth가 "요청한 스코프가 허가되지 않았다"며
# 갱신 자체를 거부한다. 읽기는 이 스코프로도 된다.
SCOPES = ["https://www.googleapis.com/auth/youtube"]
REQUIRED_ENV = ("WEIRD_CLIENT_ID", "WEIRD_CLIENT_SECRET", "WEIRD_REFRESH_TOKEN")

# videos.list는 한 번에 50개까지 받는다.
BATCH = 50


def uploaded_videos(log_path: Path) -> list[tuple[str, str, str]]:
    """(youtube_video_id, content_id, type) 목록. 중복 id는 한 번만."""
    if not log_path.exists():
        return []

    seen: dict[str, tuple[str, str, str]] = {}
    with open(log_path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            video_id = (row.get("youtube_video_id") or "").strip()
            if video_id and row.get("status") == "uploaded":
                seen[video_id] = (
                    video_id,
                    (row.get("content_id") or "").strip(),
                    (row.get("type") or "").strip(),
                )
    return list(seen.values())


def get_credentials() -> Credentials:
    missing = [n for n in REQUIRED_ENV if not os.environ.get(n)]
    if missing:
        raise RuntimeError("필수 시크릿이 없습니다: " + ", ".join(missing))

    creds = Credentials(
        token=None,
        refresh_token=os.environ["WEIRD_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["WEIRD_CLIENT_ID"],
        client_secret=os.environ["WEIRD_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def fetch_statistics(video_ids: list[str]) -> dict[str, dict]:
    youtube = build("youtube", "v3", credentials=get_credentials())
    stats: dict[str, dict] = {}
    for i in range(0, len(video_ids), BATCH):
        chunk = video_ids[i : i + BATCH]
        resp = youtube.videos().list(part="statistics", id=",".join(chunk)).execute()
        for item in resp.get("items", []):
            stats[item["id"]] = item.get("statistics", {})
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    targets = uploaded_videos(USED_LOG)
    if not targets:
        print("[안내] 업로드된 영상이 없어 수집할 것이 없습니다.", file=sys.stderr)
        return 0

    try:
        stats = fetch_statistics([t[0] for t in targets])
    except (RuntimeError, HttpError, OSError) as exc:
        # 지표는 있으면 좋은 것이지 발행의 전제가 아니다. 여기서 파이프라인을
        # 세우면 수집이 막히는 날 영상도 안 올라간다.
        print(f"[경고] 지표 수집 실패, 건너뜁니다: {exc}", file=sys.stderr)
        return 0

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows = []
    for video_id, content_id, kind in targets:
        s = stats.get(video_id)
        if s is None:
            # 삭제됐거나 비공개 전환된 영상. 0으로 기록하면 주제 평균을 왜곡한다.
            print(f"[안내] 통계를 받지 못했습니다(삭제/비공개?): {video_id}", file=sys.stderr)
            continue
        rows.append({
            "fetched_at": now,
            "youtube_video_id": video_id,
            "content_id": content_id,
            "type": kind,
            "view_count": s.get("viewCount", "0"),
            "like_count": s.get("likeCount", "0"),
            # 좋아요를 끄면 likeCount 자체가 응답에서 빠진다. 0으로 두고
            # 조회수 문턱이 대신 걸러 준다.
            "comment_count": s.get("commentCount", "0"),
        })

    if args.dry_run:
        for r in rows:
            print(f"  {r['youtube_video_id']}  {r['type']:<12} "
                  f"조회 {r['view_count']:>7}  좋아요 {r['like_count']:>5}")
        return 0

    feedback.append_metrics(METRICS, rows)
    print(f"[완료] 지표 {len(rows)}편을 metrics.csv에 추가했습니다.", file=sys.stderr)

    excluded = sorted(feedback.failing_types(METRICS, USED_LOG))
    print(f"[판정] 제외 대상 주제: {', '.join(excluded) if excluded else '없음'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
