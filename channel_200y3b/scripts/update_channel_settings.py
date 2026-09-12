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

# Keywords lean long-form now. Shorts watch time does not count toward the
# Partner Programme's 3,000 valid public watch hours, so the terms that
# matter for that number are the listening/shadowing/compilation ones —
# but the Shorts terms stay, since Shorts is still what feeds discovery.
DEFAULT_KEYWORDS = [
    # core
    "영어공부", "영어회화", "매일영어한마디", "영어표현", "생활영어",
    "영어단어", "영어숙어", "생활영어회화", "영어공부혼자하기",
    # long-form intent
    "영어쉐도잉", "쉐도잉", "영어듣기", "영어리스닝", "흘려듣기",
    "영어몰아듣기", "수면영어", "잠들기전영어", "상황별영어", "영어회화연습",
    # use cases
    "여행영어", "비즈니스영어", "미드영어", "영화영어", "원어민표현",
    "오픽", "토익스피킹",
    # english-language discovery
    "english expressions", "daily english", "learn english",
    "english shadowing", "english listening", "korean english",
    "shorts",
]

DEFAULT_DESCRIPTION = (
    "매일 영어 한마디 — 실생활에서 바로 쓰는 영어 표현을 매일 전해드립니다.\n"
    "\n"
    "[ 업로드 일정 ]\n"
    "매일 09시·15시·21시 — 오늘의 표현 한 개\n"
    "매주 일요일 — 이번 주 표현 몰아듣기 (12분)\n"
    "매주 월요일 — 쉐도잉 트레이닝, 따라 말하기 (28분)\n"
    "매주 수요일 — 상황별 표현 팩 (35분)\n"
    "격주 금요일 — 자면서 듣는 영어 (62분)\n"
    "매월 말 — 이번 달 총정리 (70분)\n"
    "\n"
    "출퇴근길에 틀어놓고 소리 내어 따라 말하기만 해도 입이 트입니다.\n"
    "공항·호텔·식당·회의·병원까지, 그 상황에서 바로 나오는 문장을 통째로 익히세요.\n"
    "\n"
    "#영어공부 #영어회화 #매일영어한마디 #영어쉐도잉 #영어듣기 #dailyenglish"
)

# YouTube's own limits; exceeding either makes the update fail server-side.
KEYWORDS_MAX = 500
DESCRIPTION_MAX = 1000


def format_keywords(keywords) -> str:
    """Space-separated, quoting only the ones containing a space.

    Quoting every term (the previous behaviour) burns two characters each
    against the 500-character cap for no benefit.
    """
    return " ".join(f'"{kw}"' if " " in kw else kw for kw in keywords)


CHANNEL_ID = "UCeXsmdfyW4hoxgWV2K8EwFw"  # @200-y3b


def credential(name: str) -> str:
    """Prefer this channel's own secret over the shared one.

    YT_* is shared with another channel in this repo and was rotated out
    from under @200-y3b once already. Rewriting the wrong channel's
    description and keywords would be a genuinely annoying thing to undo.
    """
    value = os.environ.get(f"Y3B_{name}") or os.environ.get(f"YT_{name}")
    if not value:
        raise SystemExit(
            f"Missing credential {name}. Set Y3B_{name} (preferred) or YT_{name}."
        )
    return value


def get_credentials() -> Credentials:
    creds = Credentials(
        token=None,
        refresh_token=credential("REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=credential("CLIENT_ID"),
        client_secret=credential("CLIENT_SECRET"),
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
    if channel_id != CHANNEL_ID:
        title = channel.get("snippet", {}).get("title", "?")
        print(f"Refusing to edit: credentials belong to {channel_id} ({title}), "
              f"not @200-y3b ({CHANNEL_ID}).", file=sys.stderr)
        return 1

    branding = channel.get("brandingSettings", {})
    channel_branding = branding.setdefault("channel", {})

    changes = []

    if args.force or not field(channel_branding, "keywords"):
        keywords = format_keywords(DEFAULT_KEYWORDS)
        if len(keywords) > KEYWORDS_MAX:
            print(f"Keywords are {len(keywords)} chars, over the "
                  f"{KEYWORDS_MAX} limit.", file=sys.stderr)
            return 1
        channel_branding["keywords"] = keywords
        changes.append(f"keywords ({len(DEFAULT_KEYWORDS)} terms, {len(keywords)} chars)")

    if args.force or not field(channel_branding, "description"):
        if len(DEFAULT_DESCRIPTION) > DESCRIPTION_MAX:
            print(f"Description is {len(DEFAULT_DESCRIPTION)} chars, over the "
                  f"{DESCRIPTION_MAX} limit.", file=sys.stderr)
            return 1
        channel_branding["description"] = DEFAULT_DESCRIPTION
        changes.append(f"description ({len(DEFAULT_DESCRIPTION)} chars)")

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
