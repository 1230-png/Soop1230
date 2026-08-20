"""Upload one generated short to YouTube using a stored refresh token.

Reads YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN from environment
(GitHub Actions secrets — see ../SETUP.md). No user interaction, no browser.
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

SCOPES = ["https://www.googleapis.com/auth/youtube"]


def get_credentials() -> Credentials:
    client_id = os.environ["YT_CLIENT_ID"]
    client_secret = os.environ["YT_CLIENT_SECRET"]
    refresh_token = os.environ["YT_REFRESH_TOKEN"]

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def upload(video_id: str, privacy_status: str) -> str:
    video_path = OUTPUT_DIR / f"{video_id}.mp4"
    meta_path = OUTPUT_DIR / f"{video_id}.json"

    if not meta_path.exists():
        print(f"❌ Error: {meta_path} not found")
        sys.exit(1)

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))

    youtube = build("youtube", "v3", credentials=get_credentials())

    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": metadata["category_id"],
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()

    youtube_video_id = response["id"]
    print(f"✅ Uploaded: {youtube_video_id}")
    return youtube_video_id


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--video-id', required=True, help='Video ID to upload')
    parser.add_argument('--privacy-status', default='public', choices=['public', 'unlisted', 'private'])
    args = parser.parse_args()

    upload(args.video_id, args.privacy_status)
