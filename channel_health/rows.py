"""metrics.csv · channel_stats.csv 를 읽는 공용 도구.

report.py 와 monetization.py 가 같은 해석 규칙을 써야 해서 여기 모았다.
두 쪽에 같은 함수를 따로 두면 한쪽만 고친 날 보고서의 두 문단이 서로 다른
기준으로 같은 채널을 말한다.

**읽기만 한다.**
"""

import csv
from datetime import datetime, timezone
from pathlib import Path

# 숏폼·롱폼을 가르는 우리 기준. 유튜브의 분류와 정확히 같다고 보지 말 것 —
# 보고서를 읽기 위한 칸막이지 채널 설정이 아니다.
SHORT_MAX_SECONDS = 180


def load_rows(path):
    """CSV 를 dict 목록으로. 파일이 없으면 빈 목록."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def as_int(value):
    """빈 칸은 None. 0 과 구별한다.

    좋아요를 끈 영상과 아무도 안 누른 영상은 다르고, 구독자를 숨긴 채널과
    구독자가 0 인 채널도 다르다. 여기서 뭉개면 보고서가 없는 값을 0 으로
    말한다.
    """
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def when(value):
    """ISO 시각을 datetime 으로. 못 읽으면 None. 시간대가 없으면 UTC 로 본다."""
    text = (value or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def snapshots(rows, channel_name):
    """이 채널의 스냅샷 시각을 오래된 순으로."""
    return sorted({row["observed_at"] for row in rows
                   if row.get("channel") == channel_name})


def at_snapshot(rows, channel_name, observed_at):
    return [row for row in rows if row.get("channel") == channel_name
            and row.get("observed_at") == observed_at]


def latest_snapshot(rows, channel_name):
    """가장 최근 스냅샷의 줄들. 없으면 빈 목록."""
    stamps = snapshots(rows, channel_name)
    return at_snapshot(rows, channel_name, stamps[-1]) if stamps else []


def is_short(row):
    seconds = as_int(row.get("duration_s"))
    # 길이를 모르면 롱폼으로 둔다. 숏폼으로 잘못 넣으면 롱폼 통계가
    # 조용히 얇아지는데, 롱폼 쪽이 이 채널들이 보려는 숫자다.
    return seconds is not None and seconds <= SHORT_MAX_SECONDS


def median(numbers):
    ordered = sorted(numbers)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def views(rows):
    return [value for value in (as_int(row.get("views")) for row in rows)
            if value is not None]
