"""이미 올린 공개 영상의 설명란에 쿠팡 교재 링크와 고지를 붙인다.

    python3 channel_jp/add_affiliate.py [--dry-run]

새로 올리는 영상은 upload.py 의 video_body 가 붙인다. 이것은 그 전에 올라간
영상을 한 번 따라잡게 하려는 것이다. 링크가 이미 있는 영상은 건드리지 않으므로
여러 번 돌려도 같다.

자격 증명과 채널 확인은 upload.youtube_client 를 그대로 쓴다 — MV_* 만 받고,
채널이 MV_CHANNEL_ID 와 다르면 멈춘다.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import upload  # noqa: E402

DESCRIPTION_LIMIT = 5000


def public_videos(youtube, channel_id: str) -> list:
    uploads = "UU" + channel_id[2:]
    ids, token = [], None
    while True:
        page = youtube.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=50,
            pageToken=token).execute()
        ids += [item["contentDetails"]["videoId"] for item in page["items"]]
        token = page.get("nextPageToken")
        if not token:
            break
    videos = []
    for start in range(0, len(ids), 50):
        videos += youtube.videos().list(
            part="snippet,status", id=",".join(ids[start:start + 50])
        ).execute()["items"]
    return [v for v in videos if v["status"]["privacyStatus"] == "public"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="무엇이 바뀌는지만 보고 보내지 않는다")
    args = parser.parse_args()

    youtube = upload.youtube_client(os.environ)
    channel_id = os.environ[upload.CHANNEL_ID_ENV].strip()

    changed = 0
    for video in public_videos(youtube, channel_id):
        snippet = video["snippet"]
        new = upload.with_affiliate(snippet.get("description", ""))
        if new == snippet.get("description", ""):
            print(f"그대로  {video['id']}  {snippet['title'][:40]}")
            continue
        if len(new) > DESCRIPTION_LIMIT:
            print(f"건너뜀(길이) {video['id']}")
            continue
        print(f"{'바꿀 것' if args.dry_run else '바꿈'}  {video['id']}  {snippet['title'][:40]}")
        if not args.dry_run:
            keep = ("title", "categoryId", "tags", "defaultLanguage",
                    "defaultAudioLanguage")
            body = {"id": video["id"],
                    "snippet": {k: snippet[k] for k in keep if k in snippet}}
            body["snippet"]["description"] = new
            youtube.videos().update(part="snippet", body=body).execute()
        changed += 1

    print(f"\n{'바꿀' if args.dry_run else '바꾼'} 영상 {changed}편")
    return 0


if __name__ == "__main__":
    sys.exit(main())
