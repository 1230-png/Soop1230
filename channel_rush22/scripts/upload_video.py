"""Upload a rendered Short to the @Rush22 YouTube channel.

Credentials come from RUSH_* environment variables only. Several channels in
this repo publish to YouTube, and letting them share one set of YT_* secrets
has already caused one channel's videos to break — and, had the rotation gone
the other way, would have published them to the wrong channel instead. There
is deliberately no fallback here: missing RUSH_* credentials fail the run
rather than quietly borrowing another channel's.
"""

import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env.youtube"
SCOPES = ["https://www.googleapis.com/auth/youtube"]

# The channel this script is allowed to publish to. Uploading to the wrong
# channel is silent and painful to undo, so it is checked before every upload.
# The handle is matched when RUSH_CHANNEL_ID is not set; setting the id is
# stricter and preferred, since handles can be changed by the channel owner.
EXPECTED_HANDLE = "@rush22-i8p"
CATEGORY_EDUCATION = "27"


def _load_env_file() -> None:
    """Pull RUSH_* values from .env.youtube (written by get_refresh_token.py)
    so local runs work without exporting anything by hand."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _assert_target_channel(youtube) -> None:
    resp = youtube.channels().list(part="id,snippet", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        raise SystemExit("Could not determine which channel these credentials belong to.")

    actual_id = items[0]["id"]
    snippet = items[0]["snippet"]
    actual_handle = (snippet.get("customUrl") or "").lower()
    title = snippet.get("title", "?")

    expected_id = os.environ.get("RUSH_CHANNEL_ID")
    if expected_id:
        if actual_id != expected_id:
            raise SystemExit(
                f"Refusing to upload: credentials belong to {actual_id} ({title}), "
                f"not the configured RUSH_CHANNEL_ID ({expected_id})."
            )
        return

    if actual_handle != EXPECTED_HANDLE:
        raise SystemExit(
            f"Refusing to upload: credentials belong to {actual_handle or actual_id} "
            f"({title}), not {EXPECTED_HANDLE}.\n"
            f"If the channel handle changed, set RUSH_CHANNEL_ID={actual_id} "
            "as a repository secret to pin it by id instead."
        )
    print(f"🔒 Verified channel: {title} ({actual_handle}, {actual_id})")


def get_youtube_client():
    _load_env_file()
    client_id = os.environ.get("RUSH_CLIENT_ID")
    client_secret = os.environ.get("RUSH_CLIENT_SECRET")
    refresh_token = os.environ.get("RUSH_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise SystemExit(
            "Missing YouTube credentials. Set all three as repository secrets:\n"
            "  RUSH_CLIENT_ID / RUSH_CLIENT_SECRET / RUSH_REFRESH_TOKEN\n"
            "See channel_rush22/SETUP.md."
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)
    _assert_target_channel(youtube)
    return youtube


def upload_short(
    video_path: Path,
    title: str,
    description: str,
    tags,
    privacy_status: str = "public",
) -> str:
    """Upload one vertical video and return its YouTube id."""
    youtube = get_youtube_client()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": CATEGORY_EDUCATION,
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            "privacyStatus": privacy_status,
            "madeForKids": False,
            "selfDeclaredMadeForKids": False,
        },
    }

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=-1),
    )
    response = request.execute()
    video_id = response["id"]
    print(f"✅ Uploaded: {title} ({video_id})")
    return video_id


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Upload a video to @Rush22")
    parser.add_argument("video_path", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--tags", default="", help="comma-separated")
    args = parser.parse_args()

    if not args.video_path.exists():
        raise SystemExit(f"Video file not found: {args.video_path}")

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    try:
        video_id = upload_short(args.video_path, args.title, args.description, tags)
    except HttpError as e:
        print(f"❌ YouTube API error: {e}", file=sys.stderr)
        return 1
    print(f"\n✨ https://youtube.com/shorts/{video_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
