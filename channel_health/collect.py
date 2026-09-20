"""채널이 낸 영상의 공개 지표를 모아 metrics.csv 에 덧붙인다.

**읽기만 한다.** 업로드도, 수정도, 댓글도 하지 않는다.

한 번 돌 때마다 그 시점의 값을 통째로 한 벌 남긴다(스냅샷). 영상마다 값을
덮어쓰지 않는 이유는, 덮어쓰면 "지금 몇 회"만 남고 "얼마나 늘고 있나"가
사라지기 때문이다. 늘어나는 속도가 있어야 어제 바꾼 것이 먹혔는지 알 수 있다.
used_log*.csv 와 같은 append-only 기록으로 다룬다.

**이 API 로는 시청 시간을 알 수 없다.** Data API 는 조회수·좋아요·댓글 수까지다.
파트너 프로그램이 세는 3,000시간은 YouTube Analytics API 에 있고 그쪽은
yt-analytics.readonly 스코프를 따로 받아야 한다. 지금 토큰에는 없다.
그래서 여기 숫자로는 "어느 편이 더 많이 눌렸나"까지만 말할 수 있고
"시청 시간이 쌓이고 있나"는 말할 수 없다. 섞어 읽지 말 것.

할당량: 채널 하나에 대략 3~6 units(영상 50개마다 2 units 씩 는다).
하루 한도가 프로젝트당 10,000 이라 무시할 수준이다.
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

import channels as channel_registry

ROOT = Path(__file__).resolve().parent
METRICS_PATH = ROOT / "metrics.csv"

# 구독자 수는 영상이 아니라 채널에 붙는 값이라 metrics.csv 에 넣을 자리가 없다.
# 줄마다 같은 값을 반복하는 것도 방법이지만, 이미 쌓인 파일의 헤더를 바꾸면
# 예전 줄(9칸)과 새 줄(10칸)이 섞여 DictReader 가 통째로 어긋난다.
# append-only 기록은 칸을 늘리지 않는 편이 안전하다.
STATS_PATH = ROOT / "channel_stats.csv"

PAGE_SIZE = 50

FIELDS = ("observed_at", "channel", "video_id", "published_at",
          "duration_s", "title", "views", "likes", "comments")

STATS_FIELDS = ("observed_at", "channel", "subscribers", "videos", "views")

_DURATION = re.compile(
    r"^P(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$")


class CollectError(RuntimeError):
    """자격 증명이 없거나 토큰이 엉뚱한 채널을 가리킨다."""


def parse_duration(text):
    """ISO 8601 기간(PT1M30S)을 초로. 못 읽으면 None.

    0 을 돌려주지 않는다 — 길이를 모르는 것과 길이가 0 인 것은 다르고,
    여기서 0 으로 뭉개면 보고서가 그 영상을 숏폼으로 분류한다.
    """
    if not text:
        return None
    found = _DURATION.match(text.strip())
    if not found:
        return None
    parts = {key: int(value or 0) for key, value in found.groupdict().items()}
    return (parts["days"] * 86400 + parts["hours"] * 3600
            + parts["minutes"] * 60 + parts["seconds"])


def build_client(channel, env=None):
    """읽기 전용 유튜브 클라이언트.

    **새로고침 요청에 스코프를 싣지 않는다(scopes=None).** 발급 때보다 넓은
    스코프를 적어 보내면 구글이 invalid_scope 로 거절해서 업로드가 통째로
    죽은 적이 있다(channel_200y3b/scripts/upload_video.py 주석). 스코프는
    코드가 아니라 토큰에 붙어 있다.
    """
    env = os.environ if env is None else env
    missing = channel.credentials_missing(env)
    if missing:
        raise CollectError(
            f"{channel.label}: 자격 증명이 없다 — {', '.join(missing)}.\n"
            "  이 채널 전용 값이어야 한다. 다른 채널 것을 넣으면 그 채널 숫자가 기록된다.")

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=env[channel.refresh_token_env].strip(),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=env[channel.client_id_env].strip(),
        client_secret=env[channel.client_secret_env].strip(),
        scopes=None,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def own_channel(youtube, channel, env=None, part="contentDetails"):
    """이 토큰이 가리키는 채널 항목 하나.

    지정한 채널과 다르면 멈춘다. 틀린 채널 숫자를 이 채널 것으로 적으면,
    그 뒤로 이 파일을 근거로 내리는 판단이 전부 엉뚱한 채널을 따라간다.
    """
    env = os.environ if env is None else env
    response = youtube.channels().list(part=part, mine=True).execute()
    items = response.get("items", [])
    if not items:
        raise CollectError(f"{channel.label}: 토큰이 채널을 가리키지 않는다.")

    expected = channel.target_channel_id(env)
    if not expected and channel.channel_id_env:
        # "아직 모른다"와 "빠뜨렸다"는 다르다.
        #
        # 등록표에 채널 ID 자리를 아예 안 둔 채널은 전자다 — 새 채널을 ID
        # 없이 먼저 넣어 보는 것이 흔한 순서이고, 그 수집까지 막지는 않는다
        # (test_a_channel_without_a_known_id_is_not_blocked 가 그것을 지킨다).
        #
        # 여기는 후자다. 어디서 읽을지까지 적어 놓고 그 값이 비었다면 그것은
        # 시크릿을 빠뜨린 것이다. 그냥 지나가면 남의 채널 숫자가 이 채널
        # 이름으로 쌓이고, 그 뒤 판단이 전부 엉뚱한 채널을 따라간다.
        # 한 채널이 멈춰도 나머지는 그대로 기록된다(main 이 채널마다 따로 받는다).
        raise CollectError(
            f"{channel.label}: 어느 채널이어야 하는지 모른다 — "
            f"{channel.channel_id_env} 를 넣을 것. 짐작해서 기록하지 않는다.")
    actual = [item["id"] for item in items]
    if expected and expected not in actual:
        raise CollectError(
            f"{channel.label}: 토큰이 가리키는 채널({actual})이 지정한 채널"
            f"({expected})과 다르다. 기록하지 않는다.")
    return items[0]


def uploads_playlist(youtube, channel, env=None):
    """이 토큰이 가리키는 채널의 '업로드' 재생목록 ID."""
    item = own_channel(youtube, channel, env, part="contentDetails")
    related = item.get("contentDetails", {}).get("relatedPlaylists", {})
    playlist = related.get("uploads")
    if not playlist:
        raise CollectError(f"{channel.label}: 업로드 재생목록을 찾지 못했다.")
    return playlist


def channel_stats(youtube, channel, observed_at, env=None):
    """구독자 수 한 줄. 수익화 거리의 절반이 이 숫자다.

    구독자를 숨긴 채널은 subscriberCount 가 아예 오지 않는다. 0 으로 적지
    않고 빈 칸으로 둔다 — 없는 것과 0 은 다르다.
    """
    item = own_channel(youtube, channel, env, part="statistics")
    stats = item.get("statistics", {})
    return {
        "observed_at": observed_at,
        "channel": channel.name,
        "subscribers": stats.get("subscriberCount", ""),
        "videos": stats.get("videoCount", ""),
        "views": stats.get("viewCount", ""),
    }


def video_ids(youtube, playlist_id):
    """업로드 재생목록의 영상 ID 를 전부. 페이지를 끝까지 따라간다."""
    ids, page = [], None
    while True:
        response = youtube.playlistItems().list(
            part="contentDetails", playlistId=playlist_id,
            maxResults=PAGE_SIZE, pageToken=page).execute()
        for item in response.get("items", []):
            found = item.get("contentDetails", {}).get("videoId")
            if found:
                ids.append(found)
        page = response.get("nextPageToken")
        if not page:
            return ids


def video_rows(youtube, ids, channel_name, observed_at):
    """영상 ID 목록을 지표 줄로. 50개씩 끊어 부른다."""
    rows = []
    for start in range(0, len(ids), PAGE_SIZE):
        batch = ids[start:start + PAGE_SIZE]
        response = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(batch)).execute()
        for item in response.get("items", []):
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})
            duration = parse_duration(
                item.get("contentDetails", {}).get("duration"))
            rows.append({
                "observed_at": observed_at,
                "channel": channel_name,
                "video_id": item.get("id", ""),
                "published_at": snippet.get("publishedAt", ""),
                "duration_s": "" if duration is None else duration,
                "title": snippet.get("title", ""),
                # 없는 것과 0 은 다르다. 좋아요·댓글을 끈 영상은 아예 키가
                # 오지 않는데 0 으로 적으면 "아무도 안 눌렀다"로 읽힌다.
                "views": stats.get("viewCount", ""),
                "likes": stats.get("likeCount", ""),
                "comments": stats.get("commentCount", ""),
            })
    return rows


class Collected(NamedTuple):
    """한 채널에서 한 번에 읽어 온 것. 두 파일로 나뉘어 저장된다."""

    videos: list
    stats: dict


def collect(channel, youtube=None, env=None, now=None):
    """한 채널의 지표를 만든다. 파일에는 쓰지 않는다.

    영상 지표와 구독자 수를 **같은 시각(observed_at)으로** 묶는다. 따로 읽으면
    두 파일의 스냅샷이 어긋나서 "이때 구독자가 몇이었나"를 짝지을 수 없다.
    """
    env = os.environ if env is None else env
    observed_at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    if youtube is None:
        youtube = build_client(channel, env)
    playlist = uploads_playlist(youtube, channel, env)
    videos = video_rows(youtube, video_ids(youtube, playlist),
                        channel.name, observed_at)
    return Collected(videos, channel_stats(youtube, channel, observed_at, env))


def append_rows(rows, path=METRICS_PATH, fields=FIELDS):
    """스냅샷을 덧붙인다. 기존 줄은 건드리지 않는다."""
    if not rows:
        return 0
    path = Path(path)
    fresh = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if fresh:
            writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--channel", action="append", dest="names",
                        choices=sorted(channel_registry.BY_NAME),
                        help="기본값은 전부")
    parser.add_argument("--metrics-path", default=str(METRICS_PATH))
    parser.add_argument("--stats-path", default=str(STATS_PATH))
    args = parser.parse_args(argv)

    wanted = [channel_registry.BY_NAME[name] for name in args.names] \
        if args.names else list(channel_registry.CHANNELS)

    total, failed = 0, []
    for channel in wanted:
        try:
            result = collect(channel)
        except CollectError as error:
            # 한 채널이 안 된다고 나머지를 포기하지 않는다. 채널마다 자격
            # 증명이 따로라 한쪽만 만료되는 일이 실제로 생긴다.
            print(f"⚠️  {error}", file=sys.stderr)
            failed.append(channel.name)
            continue
        except Exception as error:      # noqa: BLE001 — 네트워크·API 오류
            print(f"⚠️  {channel.label}: 수집 실패 — {error}", file=sys.stderr)
            failed.append(channel.name)
            continue
        written = append_rows(result.videos, args.metrics_path)
        append_rows([result.stats], args.stats_path, STATS_FIELDS)
        total += written
        subs = result.stats.get("subscribers") or "비공개"
        print(f"  {channel.label}: 영상 {written}편 기록 (구독자 {subs})")

    if not total:
        print("::error::아무 채널도 읽지 못했다.", file=sys.stderr)
        return 1
    if failed:
        print(f"::warning::읽지 못한 채널: {', '.join(failed)}", file=sys.stderr)
    print(f"모두 {total}줄 덧붙였다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
