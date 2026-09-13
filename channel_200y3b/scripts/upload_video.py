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
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
# 댓글 API(commentThreads)는 youtube 스코프로는 403 insufficientPermissions 를
# 낸다. youtube.force-ssl 이 필요하고, 이쪽이 youtube 의 상위 집합이다.
#
# 기존 토큰이 youtube 만 가지고 있어도 새로고침은 그대로 된다 — google-auth 는
# 요청 스코프가 부여 스코프보다 넓으면 경고만 남긴다. 그래서 업로드는 지금도
# 돌고, 토큰을 다시 발급받는 순간 댓글이 따라서 켜진다.
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
ENV_FILE = ROOT / ".env.youtube"

# Coupang Partners affiliate link — must be generated per-product at
# partners.coupang.com (there's no formula to construct a working coupa.ng
# link from just a partner ID). Empty until a real link is added.
COUPANG_LINK = ""

CHANNEL_ID = "UCeXsmdfyW4hoxgWV2K8EwFw"  # @200-y3b

# 쇼츠 시청 시간은 파트너 프로그램의 유효 공개 시청 시간에 들어가지 않는다.
# 그 숫자를 움직이는 것은 롱폼뿐이고, 쇼츠가 가진 것은 사람이다. 설명란은
# 쇼츠에서 거의 펼쳐지지 않으므로 댓글로도 같은 길을 낸다.
#
# 고정(pin)은 Data API 에 없다 — 스튜디오에서만 된다. 여기서 다는 것은 고정
# 안 된 채널 댓글이다.
LONGFORM_COMMENT = (
    "🎧 이 표현들 몰아듣기 — 롱폼 재생목록\n"
    "https://www.youtube.com/@200-y3b/playlists\n"
    "\n"
    "일요일 주간 복습 · 월요일 쉐도잉 · 수요일 상황별 · 금요일 자면서 듣는 영어\n"
    "출퇴근길에 틀어 두기 좋게 만들었습니다."
)


def _post_longform_comment(youtube, video_id: str) -> None:
    """업로드 직후 롱폼으로 가는 채널 댓글을 단다.

    실패해도 업로드는 이미 끝났다. 여기서 예외를 올리면 워크플로가 실패로
    끝나고 used_log 가 기록되지 않아, 다음 실행이 같은 표현을 또 올린다.
    """
    try:
        youtube.commentThreads().insert(
            part="snippet",
            body={"snippet": {
                "videoId": video_id,
                "topLevelComment": {
                    "snippet": {"textOriginal": LONGFORM_COMMENT}},
            }},
        ).execute()
        print(f"✅ Long-form comment posted on {video_id}")
    except HttpError as e:
        print(f"⚠️  Comment failed (ignored): {e}", file=sys.stderr)


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


def _get_or_create_playlist(youtube, title: str) -> str:
    """Return the id of the channel's playlist with this title, creating it
    if it doesn't exist yet. Grouping videos into playlists gives autoplay-
    into-next-video watch time (a real lever on watch hours, which is one of
    the two YouTube Partner Program eligibility tracks)."""
    page_token = None
    while True:
        resp = youtube.playlists().list(
            part="id,snippet", mine=True, maxResults=50, pageToken=page_token
        ).execute()
        for item in resp.get("items", []):
            if item["snippet"]["title"] == title:
                return item["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    resp = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": title},
            "status": {"privacyStatus": "public"},
        },
    ).execute()
    return resp["id"]


# A playlist created seconds ago is not reliably visible to the very next
# call: the long-form uploader created one and then got 409 SERVICE_UNAVAILABLE
# ("The operation was aborted.") inserting into it. That is a propagation
# race rather than a rejection, so it is worth waiting out. This side has not
# hit it only because its playlists already exist.
_RETRY_STATUSES = {409, 500, 502, 503}


def _add_to_playlist(youtube, video_id: str, playlist_title: str,
                     attempts: int = 4) -> None:
    try:
        playlist_id = _get_or_create_playlist(youtube, playlist_title)
    except HttpError as e:
        print(f"⚠️  Could not resolve playlist '{playlist_title}': {e}", file=sys.stderr)
        return

    for attempt in range(1, attempts + 1):
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }
                },
            ).execute()
            print(f"✅ Added {video_id} to playlist '{playlist_title}'")
            return
        except HttpError as e:
            if e.resp.status not in _RETRY_STATUSES or attempt == attempts:
                print(f"⚠️  Could not add {video_id} to playlist "
                      f"'{playlist_title}': {e}", file=sys.stderr)
                return
            wait = 5 * attempt
            print(f"⏳ Playlist insert got {e.resp.status}, retrying in {wait}s "
                  f"({attempt}/{attempts - 1})", file=sys.stderr)
            time.sleep(wait)


def upload_video(
    video_path: Path,
    title: str,
    description: str,
    thumbnail_path: Path = None,
    category_id: str = "27",  # Education
    privacy_status: str = "public",
    playlist_title: str = None,
) -> str:
    """Upload video to YouTube and return video ID.

    Args:
        video_path: Path to .mp4 file
        title: Video title
        description: Video description (affiliate link will be appended)
        thumbnail_path: Optional custom thumbnail image path
        category_id: YouTube category (27=Education)
        privacy_status: 'public', 'unlisted', or 'private'
        playlist_title: Optional playlist name to add this video to

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

    if playlist_title:
        _add_to_playlist(youtube, video_id, playlist_title)

    _post_longform_comment(youtube, video_id)

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
    parser.add_argument("--playlist", help="Optional playlist name to add this video to")
    args = parser.parse_args()

    if not args.video_path.exists():
        raise SystemExit(f"Video file not found: {args.video_path}")

    try:
        video_id = upload_video(
            args.video_path,
            args.title,
            args.description,
            args.thumbnail,
            playlist_title=args.playlist,
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
