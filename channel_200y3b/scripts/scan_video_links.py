"""Scan every video on the channel and report any URLs found in the
description, so you can eyeball whether any are broken/leftover links.

Run locally:
    python scan_video_links.py
"""

import re
import sys

from upload_video import CHANNEL_ID, get_youtube_client

URL_RE = re.compile(r"https?://\S+")


def get_uploads_playlist_id(youtube) -> str:
    resp = youtube.channels().list(part="contentDetails", id=CHANNEL_ID).execute()
    return resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def iter_video_ids(youtube, playlist_id: str):
    page_token = None
    while True:
        resp = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=page_token,
        ).execute()
        for item in resp.get("items", []):
            yield item["contentDetails"]["videoId"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def main():
    youtube = get_youtube_client()
    playlist_id = get_uploads_playlist_id(youtube)

    video_ids = list(iter_video_ids(youtube, playlist_id))
    print(f"Found {len(video_ids)} videos on channel.\n")

    any_links = False
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        resp = youtube.videos().list(part="snippet", id=",".join(batch)).execute()
        for item in resp["items"]:
            title = item["snippet"]["title"]
            description = item["snippet"]["description"]
            urls = URL_RE.findall(description)
            if urls:
                any_links = True
                print(f"🔗 {item['id']} — {title}")
                for url in urls:
                    print(f"     {url}")
                print()

    if not any_links:
        print("✅ No links found in any video description.")


if __name__ == "__main__":
    sys.exit(main())
