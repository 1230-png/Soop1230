"""이번 주·이번 달에 다룬 조건을 한 편으로 묶는 몰아보기.

**여기는 소재 반복 금지의 예외다.** 평소 `topics.next_topic()` 은 이미 다룬 key 를
건너뛴다. 몰아보기는 정반대로 **이미 다룬 것만** 모은다 — 같은 조건을 새 회차인
척 다시 내는 것이 아니라, 지난 회차들을 한자리에 모아 "이번 주에 확인한 것"으로
묶는 것이기 때문이다. 시청자에게 이것은 반복이 아니라 정리다.

이 편이 따로 필요한 이유는 시청 시간이다. 숏폼 시청 시간은 파트너 프로그램의
3,000시간에 들어가지 않는다(`longform/README.md` 와 같은 이유). 이미 만든 회차를
묶어 긴 한 편을 내는 것은 새 소재를 쓰지 않고 시청 시간을 쌓는 유일한 경로다.

기록에서 되살리는 방식이라 `out/` 에 남은 파일에 기대지 않는다. 그 폴더는
gitignore 이고 아티팩트도 30일이면 사라진다. `used_topics.csv` 의 key 만 있으면
그때 쓴 도구 인자를 다시 세울 수 있어서(`topics.topic_by_key` ·
`news_topics.topic_from_key`), 블록은 코드가 처음부터 다시 뽑는다. 숫자가 다시
계산되는 것이 아니라 **같은 코드가 같은 조건으로 다시 뽑는 것**이라 원 회차와
같은 값이 나온다.
"""

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import news_topics, topics

# 한국 시각 기준으로 주·달을 가른다. 발행이 한국 아침이라 UTC 로 자르면
# 월요일 새벽 회차가 지난주로 밀린다.
KST = timezone(timedelta(hours=9))

WEEK = "week"
MONTH = "month"
WINDOWS = (WEEK, MONTH)

# 이만큼은 모여야 묶을 거리가 된다. 한 편짜리 "몰아보기"는 원 회차의 재탕이다.
MIN_EPISODES = 2

RECAP_TOOL = "recap"


def window_bounds(kind, now=None):
    """(시작, 끝) 을 KST 기준으로 돌려준다. 끝은 열린 구간이다."""
    if kind not in WINDOWS:
        raise ValueError(f"모르는 구간: {kind}")
    now = (now or datetime.now(timezone.utc)).astimezone(KST)
    if kind == WEEK:
        # 월요일 00:00 부터. weekday() 는 월=0 이다.
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, now


def window_key(kind, now=None):
    """구간마다 하나뿐인 key. 같은 주를 두 번 묶지 않으려고 쓴다."""
    start, _ = window_bounds(kind, now)
    if kind == WEEK:
        year, week, _ = start.isocalendar()
        return f"recap-week-{year}-W{week:02d}"
    return f"recap-month-{start:%Y-%m}"


def _rows(log_path):
    path = Path(log_path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def episodes_in_window(kind, log_path=topics.LOG_PATH, now=None):
    """구간 안에서 실제로 발행한 회차들. 오래된 것부터.

    몰아보기 자신은 제외한다 — 묶은 것을 또 묶으면 같은 영상이 겹겹이 쌓인다.
    """
    start, end = window_bounds(kind, now)
    found = []
    for row in _rows(log_path):
        if row.get("tool") == RECAP_TOOL:
            continue
        stamp = row.get("date") or ""
        try:
            when = datetime.fromisoformat(stamp)
        except ValueError:
            continue  # 형식이 깨진 줄 하나 때문에 묶기를 포기하지 않는다
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        when = when.astimezone(KST)
        if start <= when < end:
            found.append(row)
    return found


def resolve(row):
    """기록 한 줄을 도구 인자까지 붙은 토픽으로. 못 알아보면 None."""
    key = row.get("key") or ""
    try:
        return topics.topic_by_key(key)
    except KeyError:
        return news_topics.topic_from_key(key)


def resolve_all(rows, log=print):
    """알아본 것만 순서대로. 못 알아본 key 는 조용히 버리지 않고 남긴다."""
    found = []
    for row in rows:
        topic = resolve(row)
        if topic is None:
            log(f"  ! 알아보지 못한 소재라 건너뛴다: {row.get('key')}")
            continue
        found.append(topic)
    return found


def combine_blocks(blocks):
    """블록 여러 개를 대본이 읽을 하나로. 순서는 발행 순서다.

    검증기는 대본의 숫자가 블록 안에 있는지만 본다. 이어 붙인 블록이면
    어느 회차의 수치든 통과하므로, 구간마다 제목을 붙여 모델이 섞어 쓰지
    않도록 한다. 섞어 쓰는 것은 코드가 막지 못하고 프롬프트가 맡는다.
    """
    parts = []
    for index, (label, text) in enumerate(blocks, start=1):
        parts.append(f"=== {index}번 조건: {label} ===\n{text.strip()}")
    return "\n\n".join(parts)
