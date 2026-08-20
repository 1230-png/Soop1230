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
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Coupang Partners affiliate info
COUPANG_PARTNER_ID = "AF2646556"
COUPANG_LINK = f"https://coupa.ng/ca/{COUPANG_PARTNER_ID}/search/영어%20학습"

CHANNEL_ID = "UCEHRa1rmhcZNVm5F7Zz_ycw"  # @200-y3b


def get_youtube_client():
    """Get authorized YouTube API client using GitHub Secrets environment variables."""
    client_id = os.environ.get("YT_CLIENT_ID")
    client_secret = os.environ.get("YT_CLIENT_SECRET")
    refresh_token = os.environ.get("YT_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise SystemExit(
            "Missing YouTube OAuth credentials in environment:\n"
            "  YT_CLIENT_ID\n"
            "  YT_CLIENT_SECRET\n"
            "  YT_REFRESH_TOKEN"
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
    return build("youtube", "v3", credentials=creds)


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

    # Add Coupang Partners affiliate link to description
    full_description = f"{description}\n\n📚 추천 상품: {COUPANG_LINK}"

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
