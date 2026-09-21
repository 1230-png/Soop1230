"""채널에 올라가 있는 예전 영상을 목록으로 보고, 원하면 지운다.

    python3 channel_earth/tools/purge_videos.py                 # 목록만 (기본)
    python3 channel_earth/tools/purge_videos.py --before 2026-09-22 --delete --yes 79

**지운 영상은 되돌릴 수 없다.** 조회수도 댓글도 같이 사라진다. 그래서
기본 동작은 목록을 찍는 것뿐이고, 실제로 지우려면 두 가지를 다 줘야 한다.

- `--delete`
- `--yes N` — N 은 지울 개수와 **정확히 같아야 한다.** 목록을 눈으로 보고
  숫자를 직접 적으라는 뜻이다. `--yes-all` 같은 것은 두지 않았다

왜 이 도구가 필요한가: 이 채널은 새로 만든 것이 아니라 @Rush22 의 방향을
바꾼 것이다. 예전 숏츠가 그대로 남아 있으면 **채널의 카탈로그가 「대량 생산된
템플릿 영상 79편 + 새 영상 몇 편」으로 보인다.** 파트너 프로그램 심사는
채널 전체를 보므로, 방향을 바꿨다면 예전 것을 정리하는 편이 낫다.

할당량: 목록은 한 쪽에 1 유닛, 삭제는 한 편에 50 유닛이다. 하루 한도가
10,000 이므로 **한 번에 지울 수 있는 것은 200편 미만**이고, 같은 날 영상을
올리려면(업로드 1,600) 그만큼 빼고 세야 한다. 한도에 걸리면 멈추고 몇 편을
지웠는지 알려 준다 — 다음 날 다시 돌리면 이어서 지운다.
"""

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from googleapiclient.errors import HttpError  # noqa: E402

import channel_settings as settings  # noqa: E402

# videos.delete 한 번에 드는 값. 하루 한도 10,000 에서 역산한다.
DELETE_COST = 50
DAILY_QUOTA = 10_000
# 업로드(1,600)와 재시도 여유를 남겨 둔다. 전부 삭제에 쓰면 그날은 발행을 못 한다.
RESERVE = 2_500


def uploads_playlist(youtube, env) -> tuple[str, str]:
    """이 자격 증명이 가진 채널의 업로드 재생목록 ID.

    채널 ID 를 확인하는 것이 먼저다 — 남의 채널 영상을 지우는 실수는
    되돌릴 수가 없다. upload.py · channel_settings.py 와 같은 규칙이다.
    """
    response = youtube.channels().list(
        part="contentDetails,snippet", mine=True).execute()
    items = response.get("items", [])
    if not items:
        raise settings.SettingsError("이 자격 증명이 채널을 가리키지 않는다")
    channel = items[0]
    settings.assert_right_channel(channel, env)
    return (channel["contentDetails"]["relatedPlaylists"]["uploads"],
            channel["snippet"].get("title", "?"))


def list_videos(youtube, playlist_id: str) -> list[dict]:
    """올라가 있는 영상 전부. 오래된 것부터."""
    videos, page = [], None
    while True:
        response = youtube.playlistItems().list(
            part="snippet,contentDetails", playlistId=playlist_id,
            maxResults=50, pageToken=page).execute()
        for item in response.get("items", []):
            details = item.get("contentDetails", {})
            snippet = item.get("snippet", {})
            published = (details.get("videoPublishedAt")
                         or snippet.get("publishedAt") or "")
            videos.append({
                "id": details.get("videoId") or "",
                "title": snippet.get("title", ""),
                "published": published,
            })
        page = response.get("nextPageToken")
        if not page:
            break
    videos.sort(key=lambda v: v["published"])
    return [v for v in videos if v["id"]]


def select(videos: list[dict], before: str | None) -> list[dict]:
    """지울 후보. `--before` 가 없으면 전부다."""
    if not before:
        return list(videos)
    # 날짜만 비교한다. 유튜브가 주는 값은 RFC3339 라 앞 10자가 날짜다.
    return [v for v in videos if v["published"][:10] < before]


def main() -> int:
    parser = argparse.ArgumentParser(description="예전 영상 목록·삭제")
    parser.add_argument("--before", help="이 날짜(YYYY-MM-DD) 전에 올린 것만")
    parser.add_argument("--delete", action="store_true",
                        help="실제로 지운다. --yes 와 함께 줘야 한다")
    parser.add_argument("--yes", type=int, default=-1,
                        help="지울 개수. 목록의 개수와 정확히 같아야 한다")
    args = parser.parse_args()

    try:
        youtube = settings.youtube_client(os.environ)
        playlist, title = uploads_playlist(youtube, os.environ)
    except settings.SettingsError as error:
        print(f"멈춘다: {error}", file=sys.stderr)
        return 1

    videos = list_videos(youtube, playlist)
    targets = select(videos, args.before)
    print(f"채널 「{title}」 — 올라가 있는 영상 {len(videos)}편, "
          f"조건에 맞는 것 {len(targets)}편\n")
    for index, video in enumerate(targets, 1):
        print(f"{index:>3}. {video['published'][:10]}  {video['id']}  "
              f"{video['title'][:52]}")

    if not targets:
        return 0

    if not args.delete:
        print(f"\n목록만 찍었다. 실제로 지우려면:\n"
              f"  --delete --yes {len(targets)}")
        return 0

    if args.yes != len(targets):
        print(f"\n지우지 않는다. --yes 에 {len(targets)} 를 적어야 한다 "
              f"(받은 값: {args.yes}).\n"
              "목록을 눈으로 확인하라는 뜻이다. 되돌릴 수 없다.",
              file=sys.stderr)
        return 1

    budget = (DAILY_QUOTA - RESERVE) // DELETE_COST
    if len(targets) > budget:
        print(f"\n오늘은 {budget}편까지만 지운다 (할당량). "
              f"나머지 {len(targets) - budget}편은 내일 다시 돌릴 것.")
        targets = targets[:budget]

    print(f"\n{len(targets)}편을 지운다 — {dt.datetime.now():%H:%M:%S}")
    removed = 0
    for video in targets:
        try:
            youtube.videos().delete(id=video["id"]).execute()
            removed += 1
            print(f"  지움 {removed}/{len(targets)}  {video['id']}")
        except HttpError as error:
            reason = str(error)
            print(f"  ** 실패 {video['id']}: {reason[:120]}", file=sys.stderr)
            if "quota" in reason.lower():
                print("할당량이 끝났다. 내일 다시 돌리면 이어서 지운다.",
                      file=sys.stderr)
                break
    print(f"\n{removed}편을 지웠다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
