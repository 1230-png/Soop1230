"""Fill in EMPTY channel branding fields (keywords, description, default
language) by default — never overwrites anything the channel owner already
set. Pass --force to overwrite keywords/description regardless (used once
for the 하루 한마디 -> 매일 영어 한마디 content pivot).

Requires a refresh token with the broader 'youtube' scope (not just
'youtube.upload') — see SETUP.md.
"""

import argparse
import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/youtube"]

DEFAULT_KEYWORDS = [
    "영어공부", "영어회화", "매일영어한마디", "영어표현", "생활영어",
    "english expressions", "daily english", "learn english", "korean english",
    "영어단어", "영어숙어", "shorts",
]
DEFAULT_DESCRIPTION = (
    "매일 영어 한마디 — 실생활에서 바로 쓰는 영어 표현을 매일 전해드립니다.\n"
    "짧은 표현 하나, 뜻, 그리고 예문까지 30초 안에 배워가세요.\n\n"
    "#영어공부 #영어회화 #매일영어한마디 #dailyenglish #shorts"
)


def get_credentials() -> Credentials:
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def field(branding: dict, name: str) -> str:
    return (branding.get(name) or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite keywords/description even if already set (one-off use only).",
    )
    args = parser.parse_args()

    youtube = build("youtube", "v3", credentials=get_credentials())

    resp = youtube.channels().list(part="brandingSettings,snippet", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        print("No channel found for this account.", file=sys.stderr)
        return 1

    channel = items[0]
    channel_id = channel["id"]
    branding = channel.get("brandingSettings", {})
    channel_branding = branding.setdefault("channel", {})

    changes = []

    if args.force or not field(channel_branding, "keywords"):
        channel_branding["keywords"] = " ".join(f'"{kw}"' for kw in DEFAULT_KEYWORDS)
        changes.append("keywords")

    if args.force or not field(channel_branding, "description"):
        channel_branding["description"] = DEFAULT_DESCRIPTION
        changes.append("description")

    if not field(channel_branding, "defaultLanguage"):
        channel_branding["defaultLanguage"] = "ko"
        changes.append("defaultLanguage")

    if not changes:
        print(f"Nothing to fill in for channel {channel_id} — already set.")
        return 0

    youtube.channels().update(
        part="brandingSettings",
        body={"id": channel_id, "brandingSettings": branding},
    ).execute()

    print(f"Filled in for channel {channel_id}: {', '.join(changes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
