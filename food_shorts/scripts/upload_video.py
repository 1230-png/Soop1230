#!/usr/bin/env python3
"""Upload food shorts to YouTube."""
import json
import sys
from pathlib import Path
from datetime import datetime
import os

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def get_youtube_service():
    """Get authenticated YouTube API service."""
    client_id = os.environ.get('FOOD_CLIENT_ID')
    client_secret = os.environ.get('FOOD_CLIENT_SECRET')
    refresh_token = os.environ.get('FOOD_REFRESH_TOKEN')

    if not all([client_id, client_secret, refresh_token]):
        raise OSError("Missing YouTube credentials: set FOOD_CLIENT_ID, FOOD_CLIENT_SECRET, FOOD_REFRESH_TOKEN")

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_id,
        client_secret=client_secret
    )
    credentials.refresh(Request())
    return build('youtube', 'v3', credentials=credentials)


def upload_video(video_path, metadata_path, privacy_status='public'):
    """Upload video to YouTube."""
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if not Path(metadata_path).exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    # Load metadata
    with open(metadata_path, encoding='utf-8') as f:
        metadata = json.load(f)

    # Get YouTube service
    youtube = get_youtube_service()

    # Prepare upload body
    body = {
        'snippet': {
            'title': metadata.get('title', 'Food Short'),
            'description': metadata.get('description', ''),
            'tags': metadata.get('tags', []),
            'categoryId': '26'  # How-to & Style
        },
        'status': {
            'privacyStatus': privacy_status,
            'madeForKids': False
        }
    }

    # Upload video
    media = MediaFileUpload(video_path, chunksize=1024*1024, resumable=True)
    request = youtube.videos().insert(
        part='snippet,status',
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()

    video_id = response['id']

    # Log upload
    log_file = Path(__file__).parent.parent / "output" / "logs" / "upload_log.csv"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    with open(log_file, 'a', encoding='utf-8') as f:
        timestamp = datetime.now().isoformat()
        f.write(f"{timestamp},{video_id},{metadata.get('title', 'Unknown')}\n")

    print(f"✅ Upload complete: https://youtube.com/watch?v={video_id}")
    return video_id


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--video-path', required=True)
    parser.add_argument('--metadata-path', required=True)
    parser.add_argument('--privacy-status', default='public')
    args = parser.parse_args()

    upload_video(args.video_path, args.metadata_path, args.privacy_status)
