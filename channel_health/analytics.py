"""시청 지속률·시청 시간 — YouTube **Analytics** API 에서 읽는다.

Data API(collect.py)에는 시청 시간이 없다. 거기서 읽히는 것은 조회수까지이고,
파트너 프로그램이 세는 시간과 "사람이 끝까지 보는가"는 여기에 있다. 조회수만
보면 **어느 형식이 사람을 붙잡는지 알 수 없다** — 수면 팩과 상황별 팩 중
뭐가 나은지 물어도 답할 자료가 없었다.

**여기도 읽기만 한다.** Analytics API 에는 쓰기가 없다. channel_health 를
cron 에 걸어 둔 근거가 "올리는 것이 없다"이니 그 전제는 그대로다.

`yt-analytics.readonly` 스코프가 있어야 한다. 토큰마다 다르다 — 지금
@귀트는일본어 에는 있고 @200-y3b 에는 없다. **없는 채널은 건너뛴다.**
한 채널이 못 읽는다고 나머지 수집을 포기하지 않는다.
"""

import csv
from datetime import date, timedelta
from pathlib import Path

import collect

ROOT = Path(__file__).resolve().parent

# metrics.csv 에 칸을 늘리지 않는다. 예전 줄과 칸 수가 달라지면 DictReader 가
# 통째로 어긋난다(CLAUDE.md). 그래서 세 번째 파일이다.
RETENTION_PATH = ROOT / "retention.csv"

# scope 로 영상 줄과 채널 줄을 가른다. 섞어 두면 나중에 합계를 낼 때 영상
# 줄까지 같이 더해진다.
FIELDS = ("observed_at", "channel", "scope", "video_id", "days",
          "views", "minutes_watched", "avg_view_seconds", "avg_view_percent")

# 영상 필터에 넣을 수 있는 수에 한도가 있다. 넉넉히 잡아 나눠 보낸다.
CHUNK = 200

# 형식 비교는 **최근**을 봐야 뜻이 있다. 한 달 전에 바꾼 것이 먹혔는지 보려면
# 채널 평생 평균이 아니라 최근 창이어야 한다.
VIDEO_DAYS = 90
# 파트너 프로그램이 세는 것은 최근 12개월 공개 시청 시간이다.
CHANNEL_DAYS = 365

VIDEO_METRICS = ("views", "estimatedMinutesWatched",
                 "averageViewDuration", "averageViewPercentage")

SCOPE_HINT = (
    "토큰에 yt-analytics.readonly 가 없다. "
    "channel_jp/README.md 의 「토큰 재발급」을 볼 것.")

_COLUMN = {
    "video": "video_id",
    "views": "views",
    "estimatedMinutesWatched": "minutes_watched",
    "averageViewDuration": "avg_view_seconds",
    "averageViewPercentage": "avg_view_percent",
}


class AnalyticsError(RuntimeError):
    pass


def window(today: date, days: int) -> tuple:
    """(시작일, 끝일). 오늘을 포함한 `days` 일."""
    return (today - timedelta(days=days - 1)).isoformat(), today.isoformat()


def _blank_row(channel: str, observed_at: str, scope: str, days: int) -> dict:
    row = dict.fromkeys(FIELDS, "")
    row.update(observed_at=observed_at, channel=channel,
               scope=scope, days=str(days))
    return row


def _read(response: dict, channel: str, observed_at: str,
          scope: str, days: int) -> list:
    """응답을 줄로. **칸 이름으로 읽는다.**

    자리로 집으면 유튜브가 순서를 바꾼 날 값이 통째로 어긋나고, 그 어긋남은
    숫자가 그럴듯해서 눈에 띄지 않는다. channel_200y3b 에서 0번 칸을 집었다가
    phrase_id 가 아니라 date 를 모은 적이 있다.
    """
    names = [head.get("name", "") for head in response.get("columnHeaders", [])]
    rows = []
    for values in response.get("rows", []) or []:
        row = _blank_row(channel, observed_at, scope, days)
        for name, value in zip(names, values):
            field = _COLUMN.get(name)
            if field:
                # 빈 칸은 "모른다"다. 0 으로 채우면 "아무도 안 봤다"가 된다.
                row[field] = "" if value is None else str(value)
        rows.append(row)
    return rows


def video_rows(response: dict, channel: str, observed_at: str,
               days: int = VIDEO_DAYS) -> list:
    return _read(response, channel, observed_at, "video", days)


def channel_row(response: dict, channel: str, observed_at: str,
                days: int = CHANNEL_DAYS) -> dict:
    rows = _read(response, channel, observed_at, "channel", days)
    return rows[0] if rows else _blank_row(channel, observed_at, "channel", days)


def _query(analytics, **kwargs):
    from googleapiclient.errors import HttpError
    try:
        return analytics.reports().query(**kwargs).execute()
    except HttpError as error:
        if getattr(error, "status_code", None) == 403 or " 403 " in str(error):
            raise AnalyticsError(SCOPE_HINT) from error
        raise AnalyticsError(f"Analytics 를 읽지 못했다: {error}") from error


def fetch_video_retention(analytics, video_ids: list, start: str, end: str) -> list:
    """영상별 응답 목록. 필터 한도 때문에 나눠 묻는다."""
    responses = []
    for index in range(0, len(video_ids), CHUNK):
        chunk = video_ids[index:index + CHUNK]
        responses.append(_query(
            analytics,
            ids="channel==MINE", startDate=start, endDate=end,
            metrics=",".join(VIDEO_METRICS), dimensions="video",
            filters="video==" + ",".join(chunk), maxResults=CHUNK))
    return responses


def fetch_channel_watch(analytics, start: str, end: str) -> dict:
    return _query(analytics, ids="channel==MINE", startDate=start, endDate=end,
                  metrics="views,estimatedMinutesWatched")


def analytics_client(channel, env=None):
    """읽기 전용 Analytics 클라이언트. collect 와 같은 자격 증명을 쓴다."""
    from googleapiclient.discovery import build
    return build("youtubeAnalytics", "v2",
                 credentials=collect.credentials(channel, env))


def rows_for(channel, analytics, video_ids: list, observed_at: str,
             today: date = None) -> list:
    """이 채널에서 쌓을 줄 전부 (영상별 + 채널 합계)."""
    today = today or date.today()
    rows = []

    start, end = window(today, VIDEO_DAYS)
    for response in fetch_video_retention(analytics, video_ids, start, end):
        rows += video_rows(response, channel.name, observed_at, VIDEO_DAYS)

    start, end = window(today, CHANNEL_DAYS)
    rows.append(channel_row(fetch_channel_watch(analytics, start, end),
                            channel.name, observed_at, CHANNEL_DAYS))
    return rows


def append_rows(rows, path=RETENTION_PATH) -> int:
    """덧붙인다. 기존 줄은 건드리지 않는다 — 속도를 보려면 쌓여야 한다."""
    if not rows:
        return 0
    path = Path(path)
    fresh = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if fresh:
            writer.writeheader()
        writer.writerows(rows)
    return len(rows)
