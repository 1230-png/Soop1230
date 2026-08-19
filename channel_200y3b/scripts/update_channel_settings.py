"""Fill in EMPTY channel branding fields only (keywords, description,
default language) — never overwrites anything the channel owner already set.

Requires a refresh token with the broader 'youtube' scope (not just
'youtube.upload') — see SETUP.md.
"""

import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/youtube"]

DEFAULT_KEYWORDS = [
    "하루한마디", "위로", "동기부여", "힐링", "명언", "쇼츠", "shorts",
    "korean quotes", "motivation", "healing", "자기계발", "자존감",
    "새벽감성", "감성쇼츠", "긍정에너지",
]
DEFAULT_DESCRIPTION = (
    "하루 한마디 — 지친 하루 끝에 짧은 위로와 동기부여를 전하는 채널입니다.\n"
    "매일 새로운 한 문장으로 오늘 하루를 다독여드릴게요.\n\n"
    "#하루한마디 #위로 #동기부여 #힐링 #shorts"
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

    if not field(channel_branding, "keywords"):
        channel_branding["keywords"] = " ".join(f'"{kw}"' for kw in DEFAULT_KEYWORDS)
        changes.append("keywords")

    if not field(channel_branding, "description"):
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
