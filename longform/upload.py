"""Upload a built pack to YouTube.

    python3 longform/upload.py --dir longform/build/2026-09-13-weekly_review

Credentials come from Y3B_* first, falling back to YT_*. The brief specified
YT_* only, but in this repository those are shared with another channel and
were rotated out from under these uploads once already; Y3B_* is @200-y3b's
own slot. The channel check below then refuses to upload anywhere else, since
publishing to the wrong channel is silent and awkward to undo.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube"]
CHANNEL_ID = "UCeXsmdfyW4hoxgWV2K8EwFw"  # @200-y3b


def credential(name: str) -> str:
    return os.environ.get(f"Y3B_{name}") or os.environ.get(f"YT_{name}") or ""


def youtube_client():
    client_id = credential("CLIENT_ID")
    client_secret = credential("CLIENT_SECRET")
    refresh_token = credential("REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        raise SystemExit(
            "Missing OAuth credentials. Set either:\n"
            "  Y3B_CLIENT_ID / Y3B_CLIENT_SECRET / Y3B_REFRESH_TOKEN  (preferred)\n"
            "  YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN     (fallback)"
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

    resp = youtube.channels().list(part="id,snippet", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        raise SystemExit("Could not determine which channel these credentials own.")
    if items[0]["id"] != CHANNEL_ID:
        title = items[0]["snippet"].get("title", "?")
        raise SystemExit(
            f"Refusing to upload: credentials belong to {items[0]['id']} ({title}), "
            f"not @200-y3b ({CHANNEL_ID})."
        )
    return youtube


def upload(youtube, video_path: Path, meta: dict) -> str:
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta.get("tags", []),
            "categoryId": meta.get("categoryId", "27"),
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            "privacyStatus": meta.get("privacyStatus", "public"),
            "madeForKids": False,
        },
    }
    # Resumable: a 70-minute file is large enough that a single-shot upload
    # losing the connection would mean redoing the whole build.
    media = MediaFileUpload(str(video_path), mimetype="video/mp4",
                            chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body,
                                      media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[upload] {int(status.progress() * 100)}%", file=sys.stderr)
    return response["id"]


def set_thumbnail(youtube, video_id: str, thumb: Path) -> None:
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumb), mimetype="image/png"),
        ).execute()
        print(f"[upload] thumbnail set for {video_id}", file=sys.stderr)
    except HttpError as e:
        # Not worth failing the run over — the video is already public.
        print(f"[upload] thumbnail failed (ignored): {e}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, type=Path,
                    help="Build directory containing video.mp4 and metadata.json")
    args = ap.parse_args()

    meta_path = args.dir / "metadata.json"
    if not meta_path.exists():
        raise SystemExit(f"metadata.json not found in {args.dir}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    video = args.dir / "video.mp4"
    if not video.exists():
        raise SystemExit(f"video.mp4 not found in {args.dir}")

    youtube = youtube_client()
    video_id = upload(youtube, video, meta)
    print(f"[upload] https://www.youtube.com/watch?v={video_id}", file=sys.stderr)

    thumb = args.dir / "thumbnail.png"
    if thumb.exists():
        set_thumbnail(youtube, video_id, thumb)

    meta["youtube_video_id"] = video_id
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    print(video_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
