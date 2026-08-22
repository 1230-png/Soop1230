"""생성된 쇼츠를 YouTube에 업로드한다.

자격증명은 WEIRD_CLIENT_ID / WEIRD_CLIENT_SECRET / WEIRD_REFRESH_TOKEN 에서만 읽는다.
다른 채널의 시크릿으로 조용히 넘어가는 폴백은 의도적으로 두지 않았다.
그 폴백이 바로 이전에 invalid_client 오류를 일으킨 원인이었다.
"""

import argparse
import csv
import datetime
import json
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

import common

ROOT = Path(__file__).resolve().parent.parent

SCOPES = ["https://www.googleapis.com/auth/youtube"]

REQUIRED_ENV = ("WEIRD_CLIENT_ID", "WEIRD_CLIENT_SECRET", "WEIRD_REFRESH_TOKEN")

# 재시도해도 소용없고 오히려 할당량만 더 태우는 오류들.
FATAL_REASONS = {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded"}


def get_credentials() -> Credentials:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise EnvironmentError(
            "필수 시크릿이 없습니다: " + ", ".join(missing) + "\n"
            "GitHub → Settings → Secrets and variables → Actions 에서 "
            "정확히 이 이름으로 등록하세요. 이름이 한 글자라도 다르면 인증이 실패합니다."
        )

    creds = Credentials(
        token=None,
        refresh_token=os.environ["WEIRD_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["WEIRD_CLIENT_ID"],
        client_secret=os.environ["WEIRD_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    try:
        creds.refresh(Request())
    except Exception as exc:
        raise SystemExit(
            f"[실패] 토큰 갱신 실패: {exc}\n"
            "  invalid_client  → client_id/secret이 refresh_token과 다른 프로젝트의 것입니다.\n"
            "  invalid_grant   → refresh_token이 만료됐습니다. OAuth 동의 화면이 '테스트 중'이면\n"
            "                    토큰이 7일마다 만료됩니다. '프로덕션'으로 게시하세요.\n"
            "  두 경우 모두 get_refresh_token.py로 재발급 후 시크릿 3개를 다시 등록해야 합니다."
        ) from exc
    return creds


def upload(video_path: Path, metadata_path: Path, privacy_status: str) -> str:
    with open(metadata_path, encoding="utf-8") as f:
        metadata = json.load(f)

    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata.get("tags", []),
            "categoryId": metadata.get("category_id", "24"),
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": metadata.get("make_for_kids", False),
        },
    }

    youtube = build("youtube", "v3", credentials=get_credentials())
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    try:
        response = None
        while response is None:
            _, response = request.next_chunk()
    except HttpError as exc:
        reason = ""
        try:
            detail = json.loads(exc.content.decode("utf-8"))
            reason = detail["error"]["errors"][0].get("reason", "")
        except (ValueError, KeyError, IndexError, AttributeError):
            pass

        if reason in FATAL_REASONS:
            # 재시도가 할당량을 더 소모하므로 즉시 포기한다.
            raise SystemExit(
                f"[실패] YouTube 할당량/속도 제한에 걸렸습니다 (reason={reason}).\n"
                "  videos.insert는 1회 1,600 units이고 일일 기본 할당량은 10,000입니다.\n"
                "  재시도하지 않고 종료합니다. 내일 다시 시도하세요."
            ) from exc
        raise SystemExit(f"[실패] 업로드 오류 (reason={reason or '알 수 없음'}): {exc}") from exc

    return response["id"]


def update_log(log_path: Path, video_path: Path, video_id: str) -> None:
    """업로드 결과를 로그에 반영한다.

    헤더에 youtube_video_id / status 컬럼이 처음부터 포함돼 있어야 한다.
    (예전 스키마에는 없어서 DictWriter가 ValueError로 죽었다.)
    """
    if not log_path.exists():
        print(f"[경고] 로그가 없어 기록을 건너뜁니다: {log_path}", file=sys.stderr)
        return

    with open(log_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    for column in ("youtube_video_id", "status"):
        if column not in fieldnames:
            print(f"[경고] 로그에 '{column}' 컬럼이 없어 기록을 건너뜁니다.", file=sys.stderr)
            return

    target = video_path.name
    for row in reversed(rows):  # 같은 파일명이 여러 번 나오면 가장 최근 행을 갱신한다
        if Path(row.get("video_path", "")).name == target:
            row["youtube_video_id"] = video_id
            row["status"] = "uploaded"
            break
    else:
        print(f"[경고] 로그에서 {target} 행을 찾지 못했습니다.", file=sys.stderr)
        return

    tmp_path = log_path.with_suffix(".csv.tmp")
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(log_path)  # 원자적 교체 — 중간에 죽어도 로그가 깨지지 않는다


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-path", required=True)
    parser.add_argument("--metadata-path", required=True)
    parser.add_argument("--privacy-status", default="private",
                        choices=["public", "unlisted", "private"])
    parser.add_argument("--log-file", default="used_log.csv")
    args = parser.parse_args()

    video_path = Path(args.video_path)
    metadata_path = Path(args.metadata_path)
    log_path = ROOT / args.log_file

    for path in (video_path, metadata_path):
        if not path.exists():
            print(f"[실패] 파일이 없습니다: {path}", file=sys.stderr)
            return 1

    # 생성 단계에서 이미 검사하지만, 수동 workflow_dispatch 연타를 막기 위해 한 번 더 본다.
    # 오늘 생성된 이 영상 자신이 로그에 있으므로 uploaded 상태만 센다.
    # SKIP_DAILY_GUARD는 수동 실행에서만 켜지며, 생성 단계와 같은 값을 본다.
    uploaded_today = 0 if os.environ.get("SKIP_DAILY_GUARD") == "1" else _count_uploaded_today(log_path)
    if uploaded_today >= common.MAX_DAILY_UPLOADS:
        print(
            f"[중단] 오늘 이미 {uploaded_today}편을 업로드했습니다 "
            f"(한도 {common.MAX_DAILY_UPLOADS}). 업로드하지 않고 종료합니다.",
            file=sys.stderr,
        )
        return 0

    video_id = upload(video_path, metadata_path, args.privacy_status)
    update_log(log_path, video_path, video_id)

    print(f"[완료] https://youtu.be/{video_id}  (공개범위: {args.privacy_status})", file=sys.stderr)
    print(json.dumps({"youtube_video_id": video_id}, ensure_ascii=False))
    return 0


def _count_uploaded_today(log_path: Path) -> int:
    """오늘 날짜이면서 status가 uploaded인 행 수."""
    if not log_path.exists():
        return 0

    today = datetime.date.today().isoformat()
    count = 0
    try:
        with open(log_path, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if (row.get("date") or "").startswith(today) and row.get("status") == "uploaded":
                    count += 1
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        print(f"[경고] 로그를 읽을 수 없어 안전하게 차단합니다: {exc}", file=sys.stderr)
        return common.MAX_DAILY_UPLOADS
    return count


if __name__ == "__main__":
    sys.exit(main())
