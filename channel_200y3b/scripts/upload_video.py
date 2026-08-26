"""Upload videos to YouTube with description and optional thumbnail.

Handles:
- Video upload with metadata
- Description with Coupang Partners affiliate link
- Custom thumbnail upload (when provided)
- Log file updates
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
SCOPES = ["https://www.googleapis.com/auth/youtube"]
ENV_FILE = ROOT / ".env.youtube"

# Coupang Partners affiliate link — must be generated per-product at
# partners.coupang.com (there's no formula to construct a working coupa.ng
# link from just a partner ID). Empty until a real link is added.
COUPANG_LINK = ""

CHANNEL_ID = "UCEHRa1rmhcZNVm5F7Zz_ycw"  # @200-y3b


def _load_env_file():
    """Load YT_* values from .env.youtube (written by get_refresh_token.py)
    into os.environ if not already set, so no manual copy/paste is needed."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _credential(name: str):
    """Read one OAuth credential, preferring this channel's own secret.

    Several channels in this repo upload to YouTube and all originally read the
    same YT_* secrets. When another channel's credentials were rotated, these
    uploads broke with invalid_client — and had the rotation been consistent,
    they would instead have published @200-y3b videos to that other channel.
    Y3B_* names give this channel its own slot; YT_* stays as a fallback so
    nothing breaks before the dedicated secrets exist.
    """
    return os.environ.get(f"Y3B_{name}") or os.environ.get(f"YT_{name}")


def _assert_target_channel(youtube) -> None:
    """Abort unless the credentials actually belong to @200-y3b.

    Uploading to the wrong channel is silent and hard to undo, so this is
    checked before any upload rather than trusted."""
    resp = youtube.channels().list(part="id,snippet", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        raise SystemExit("Could not determine which channel these credentials belong to.")
    actual = items[0]["id"]
    if actual != CHANNEL_ID:
        title = items[0]["snippet"].get("title", "?")
        raise SystemExit(
            f"Refusing to upload: credentials belong to channel {actual} ({title}), "
            f"not @200-y3b ({CHANNEL_ID}).\n"
            "Set Y3B_CLIENT_ID / Y3B_CLIENT_SECRET / Y3B_REFRESH_TOKEN for this channel."
        )


def get_youtube_client():
    """Get authorized YouTube API client using GitHub Secrets environment variables."""
    _load_env_file()
    client_id = _credential("CLIENT_ID")
    client_secret = _credential("CLIENT_SECRET")
    refresh_token = _credential("REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise SystemExit(
            "Missing YouTube OAuth credentials in environment. Set either:\n"
            "  Y3B_CLIENT_ID / Y3B_CLIENT_SECRET / Y3B_REFRESH_TOKEN  (preferred)\n"
            "  YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN     (shared fallback)"
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


def upload_video(
    video_path: Path,
    title: str,
    description: str,
    thumbnail_path: Path = None,
    category_id: str = "27",  # Education
    privacy_status: str = "public",
) -> str:
    """Upload video to YouTube and return video ID.

    Args:
        video_path: Path to .mp4 file
        title: Video title
        description: Video description (affiliate link will be appended)
        thumbnail_path: Optional custom thumbnail image path
        category_id: YouTube category (27=Education)
        privacy_status: 'public', 'unlisted', or 'private'

    Returns:
        YouTube video ID
    """
    youtube = get_youtube_client()

    # Add Coupang Partners affiliate link to description, if one is set
    if COUPANG_LINK:
        full_description = f"{description}\n\n📚 추천 상품: {COUPANG_LINK}"
    else:
        full_description = description

    # Upload video
    body = {
        "snippet": {
            "title": title,
            "description": full_description,
            "tags": ["영어", "English", "학습", "매일영어"],
            "categoryId": category_id,
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            "privacyStatus": privacy_status,
            "madeForKids": False,
        },
    }

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=-1),
    )

    response = request.execute()
    video_id = response["id"]
    print(f"✅ Uploaded: {title} (Video ID: {video_id})")

    # Upload custom thumbnail if provided
    if thumbnail_path and thumbnail_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/png"),
            ).execute()
            print(f"✅ Thumbnail uploaded for {video_id}")
        except HttpError as e:
            print(f"⚠️  Thumbnail upload failed (channel may not be verified): {e}", file=sys.stderr)

    return video_id


def update_log(log_path: Path, video_id: str, **row_data):
    """Append video_id to existing log row (matching by date+phrase_id or ID)."""
    if not log_path.exists():
        print(f"⚠️  Log file {log_path} not found")
        return

    rows = []
    with open(log_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            rows.append(row)

    # Find and update last row (most recent entry)
    if rows:
        rows[-1]["youtube_video_id"] = video_id
        rows[-1]["status"] = "published"

        # Ensure youtube_video_id field exists
        if "youtube_video_id" not in fieldnames:
            fieldnames = list(fieldnames) + ["youtube_video_id", "status"]

        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"✅ Updated log: {log_path}")


def main():
    parser = argparse.ArgumentParser(description="Upload video to YouTube")
    parser.add_argument("video_path", type=Path, help="Path to video file (.mp4)")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--description", required=True, help="Video description")
    parser.add_argument("--thumbnail", type=Path, help="Optional thumbnail image")
    parser.add_argument("--log-file", type=Path, help="Log file to update")
    args = parser.parse_args()

    if not args.video_path.exists():
        raise SystemExit(f"Video file not found: {args.video_path}")

    try:
        video_id = upload_video(
            args.video_path,
            args.title,
            args.description,
            args.thumbnail,
        )

        if args.log_file:
            update_log(args.log_file, video_id)

        print(f"\n✨ Success! Video ID: {video_id}")
        return 0

    except HttpError as e:
        print(f"❌ YouTube API error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
