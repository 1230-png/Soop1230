"""채널의 설명문·키워드·기본 언어를 brand.py 값에 맞춘다.

⚠️ API로 바꿀 수 없는 것:
  - 채널 이름(title): brandingSettings.channel.title은 channels.update로 쓰이지 않는다.
  - 핸들(@이름): YouTube Data API v3에 해당 엔드포인트 자체가 없다.
  이 둘은 YouTube Studio → 맞춤설정에서 직접 바꿔야 한다. SETUP.md 참고.

기본은 '비어 있을 때만 채우기'다. 이미 손으로 설정해 둔 값을 덮어쓰려면 --force.
"""

import argparse
import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import brand

SCOPES = ["https://www.googleapis.com/auth/youtube"]
REQUIRED_ENV = ("WEIRD_CLIENT_ID", "WEIRD_CLIENT_SECRET", "WEIRD_REFRESH_TOKEN")


def get_credentials() -> Credentials:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise SystemExit("[실패] 필수 시크릿이 없습니다: " + ", ".join(missing))

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
        raise SystemExit(f"[실패] 토큰 갱신 실패: {exc}") from exc
    return creds


def field(branding: dict, name: str) -> str:
    return (branding.get(name) or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="이미 설정된 키워드/설명문도 덮어쓴다.")
    args = parser.parse_args()

    youtube = build("youtube", "v3", credentials=get_credentials())

    try:
        resp = youtube.channels().list(part="brandingSettings,snippet", mine=True).execute()
    except HttpError as exc:
        raise SystemExit(f"[실패] 채널 조회 실패: {exc}") from exc

    items = resp.get("items", [])
    if not items:
        print("[실패] 이 계정에 연결된 채널이 없습니다.", file=sys.stderr)
        return 1

    channel = items[0]
    channel_id = channel["id"]
    current_title = channel.get("snippet", {}).get("title", "?")
    branding = channel.get("brandingSettings", {})
    channel_branding = branding.setdefault("channel", {})

    changes = []
    if args.force or not field(channel_branding, "keywords"):
        channel_branding["keywords"] = " ".join(f'"{kw}"' for kw in brand.CHANNEL_KEYWORDS)
        changes.append("keywords")

    if args.force or not field(channel_branding, "description"):
        channel_branding["description"] = brand.CHANNEL_DESCRIPTION
        changes.append("description")

    if not field(channel_branding, "defaultLanguage"):
        channel_branding["defaultLanguage"] = "ko"
        changes.append("defaultLanguage")

    if not changes:
        print(f"채널 {channel_id} — 이미 모두 설정돼 있습니다. (--force로 덮어쓰기 가능)")
    else:
        try:
            youtube.channels().update(
                part="brandingSettings",
                body={"id": channel_id, "brandingSettings": branding},
            ).execute()
        except HttpError as exc:
            raise SystemExit(f"[실패] 채널 업데이트 실패: {exc}") from exc
        print(f"채널 {channel_id} 적용 완료: {', '.join(changes)}")

    if current_title != brand.CHANNEL_NAME:
        print(
            "\n" + "=" * 60 + "\n"
            f"현재 채널 이름: {current_title}\n"
            f"brand.py의 목표 이름: {brand.CHANNEL_NAME}\n"
            f"목표 핸들: {brand.CHANNEL_HANDLE}\n\n"
            "채널 이름과 핸들은 API로 바꿀 수 없습니다. YouTube Studio에서 직접 변경하세요:\n"
            "  이름 → 맞춤설정 → 브랜딩 → 이름\n"
            "  핸들 → 맞춤설정 → 기본 정보 → 핸들 (14일에 2회까지)\n"
            + "=" * 60
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
