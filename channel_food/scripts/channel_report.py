"""이 자격증명이 어느 채널에 연결돼 있고, 그 채널에 무엇이 올라가 있는지 보고한다.

영상이 채널에 안 보일 때 원인을 가르는 도구다. 비공개라서 안 보이는 것인지,
아니면 다른 채널에 올라간 것인지는 실제로 조회해 봐야 알 수 있다.

  python3 channel_report.py                    # 조회만
  python3 channel_report.py --delete ID1 ID2   # 지정한 영상 삭제 (되돌릴 수 없음)
"""

import argparse
import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/youtube"]
REQUIRED_ENV = ("WEIRD_CLIENT_ID", "WEIRD_CLIENT_SECRET", "WEIRD_REFRESH_TOKEN")


def get_credentials() -> Credentials:
    missing = [n for n in REQUIRED_ENV if not os.environ.get(n)]
    if missing:
        raise SystemExit("[실패] 필수 시크릿이 없습니다: " + ", ".join(missing))
    creds = Credentials(
        token=None,
        refresh_token=os.environ["WEIRD_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["WEIRD_CLIENT_ID"],
        client_secret=os.environ["WEIRD_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    try:
        creds.refresh(Request())
    except Exception as exc:
        raise SystemExit(f"[실패] 토큰 갱신 실패: {exc}") from exc
    return creds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", nargs="*", default=[],
                        help="삭제할 영상 ID들. 되돌릴 수 없다.")
    args = parser.parse_args()

    youtube = build("youtube", "v3", credentials=get_credentials())

    resp = youtube.channels().list(part="snippet,contentDetails,statistics", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        print("[실패] 이 자격증명에 연결된 채널이 없습니다.", file=sys.stderr)
        return 1

    ch = items[0]
    snip = ch["snippet"]
    stats = ch.get("statistics", {})
    print("=" * 60)
    print(f"채널 이름 : {snip.get('title')}")
    print(f"핸들      : {snip.get('customUrl', '(없음)')}")
    print(f"채널 ID   : {ch['id']}")
    print(f"영상 수   : {stats.get('videoCount', '?')}  구독자: {stats.get('subscriberCount', '?')}")
    print("=" * 60)

    # 업로드 재생목록에는 비공개 영상도 포함된다.
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    playlist = youtube.playlistItems().list(
        part="contentDetails", playlistId=uploads, maxResults=50
    ).execute()
    video_ids = [i["contentDetails"]["videoId"] for i in playlist.get("items", [])]

    if not video_ids:
        print("\n이 채널에 올라간 영상이 하나도 없습니다.")
        return 0

    detail = youtube.videos().list(part="snippet,status", id=",".join(video_ids)).execute()
    print(f"\n올라가 있는 영상 {len(detail.get('items', []))}개:\n")
    for v in detail.get("items", []):
        st = v["status"]
        print(f"  [{st['privacyStatus']:8}] {v['id']}  {v['snippet']['title']}")
        print(f"             업로드: {v['snippet']['publishedAt']}")
        # 예약 게시를 걸어두면 privacyStatus는 private이고 publishAt이 채워진다.
        # 그 시각이 되면 유튜브가 자동으로 공개로 바꾼다.
        if st.get("publishAt"):
            print(f"             ⏰ 예약 공개: {st['publishAt']}  (UTC 기준)")
        else:
            print(f"             ⏰ 예약 공개: 없음")

    for vid in args.delete:
        try:
            youtube.videos().delete(id=vid).execute()
            print(f"\n🗑 삭제됨: {vid}")
        except HttpError as exc:
            print(f"\n[실패] {vid} 삭제 실패: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
