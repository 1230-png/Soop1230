"""매일 다른 소재를 순환시키는 토픽 선택기.

NOTES.md 의 판단(매일 시황 요약은 하지 않는다 — 양산형 정책에 걸리고 검색 유입도
없다)은 그대로 둔다. 여기서 매일 바꾸는 것은 "오늘의 시황"이 아니라 딥다이브
대상(자산·지표·조건)이다. 형식은 항상 "이 조건이 과거에 몇 번 있었고 그 뒤
분포가 어땠나"는 에버그린 구조 그대로다.

풀에 있는 항목을 순서대로 소진하고, 이미 다룬 항목은 `used_topics.csv`
(append-only, 워크플로 실행 기록과 같은 관례)로 건너뛴다. 전부 소진하면
처음부터 다시 돈다 — 순번을 매겨 재사용 시점을 벌린다.
"""

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "used_topics.csv"
LOG_FIELDS = ["date", "key", "tool", "label"]


@dataclass(frozen=True)
class Topic:
    key: str
    tool: str  # "run" | "run_strategy" | "run_macro" | "run_tokenomics"
    argv: tuple
    label: str


# 채널 세 갈래(토크노믹스 / 매크로·유동성 / 전략 검증)를 골고루 덮는다.
# 자산·지표는 예시이며, 운영하며 얼마든지 늘릴 수 있다 — 이 목록이 유일한 원장이다.
TOPIC_POOL = (
    Topic(
        "gspc-down3", "run",
        ("--ticker", "^GSPC", "--condition", "down-weeks", "--n", "3",
         "--start", "1990-01-01", "--label", "S&P 500"),
        "S&P500 주간 3주 연속 하락",
    ),
    Topic(
        "gspc-drawdown20", "run",
        ("--ticker", "^GSPC", "--condition", "drawdown", "--pct", "20",
         "--start", "1990-01-01", "--label", "S&P 500"),
        "S&P500 고점 대비 20% 하락 첫 진입",
    ),
    Topic(
        "btc-drawdown30", "run",
        ("--ticker", "BTC-USD", "--condition", "drawdown", "--pct", "30",
         "--start", "2015-01-01", "--label", "비트코인"),
        "비트코인 고점 대비 30% 하락 첫 진입",
    ),
    Topic(
        "vix-threshold30", "run",
        ("--ticker", "^VIX", "--condition", "threshold", "--level", "30",
         "--start", "1990-01-01", "--label", "VIX"),
        "VIX 30 첫 돌파",
    ),
    Topic(
        "gspc-dca", "run_strategy",
        ("--strategy", "dca", "--ticker", "^GSPC", "--contrib-months", "12",
         "--hold-months", "36", "--start", "1990-01-01", "--label", "S&P 500"),
        "S&P500 분할매수 대 일시매수 (12개월 납입·36개월 보유)",
    ),
    Topic(
        "gspc-agg-rebalance", "run_strategy",
        ("--strategy", "rebalance", "--ticker", "^GSPC", "--ticker-b", "AGG",
         "--label", "S&P 500", "--label-b", "미국 채권(AGG)", "--start", "2003-01-01"),
        "S&P500-채권 리밸런싱 주기 비교",
    ),
    Topic(
        "yield-curve-invert", "run_macro",
        ("--series", "T10Y2Y", "--below", "0", "--ticker", "^GSPC",
         "--label", "S&P 500", "--start", "1990-01-01"),
        "장단기 금리 역전 이후 S&P500",
    ),
    Topic(
        "m2-yoy-slow", "run_macro",
        ("--series", "M2SL", "--yoy", "12", "--below", "0", "--ticker", "^GSPC",
         "--label", "S&P 500", "--start", "1990-01-01"),
        "M2 통화량 전년 대비 역성장 이후 S&P500",
    ),
    Topic(
        "btc-halving-schedule", "run_tokenomics",
        ("--mode", "schedule", "--asset", "비트코인"),
        "비트코인 반감기 발행 스케줄",
    ),
    Topic(
        "btc-dilution", "run_tokenomics",
        ("--mode", "dilution", "--coin", "bitcoin", "--asset", "비트코인"),
        "비트코인 실측 희석률",
    ),
)

_POOL_BY_KEY = {topic.key: topic for topic in TOPIC_POOL}
assert len(_POOL_BY_KEY) == len(TOPIC_POOL), "TOPIC_POOL 에 중복된 key 가 있다."


def used_keys(log_path=LOG_PATH):
    """이미 다룬 토픽 key 목록. 로그가 없으면 빈 집합."""
    path = Path(log_path)
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as file:
        return {row["key"] for row in csv.DictReader(file)}


def next_topic(log_path=LOG_PATH, pool=TOPIC_POOL):
    """아직 안 다룬 토픽 중 순서상 다음 것. 전부 소진했으면 처음부터 다시 돈다."""
    if not pool:
        raise ValueError("TOPIC_POOL 이 비어 있다.")
    done = used_keys(log_path)
    for topic in pool:
        if topic.key not in done:
            return topic
    # 전부 소진 — 가장 오래전에 쓴 것부터 다시 돈다(로그 등장 순 = 사용 순).
    return pool[0]


def record_topic(topic, log_path=LOG_PATH, when=None):
    """다룬 토픽을 append-only 로그에 남긴다. 실패한 실행은 기록하지 않는다."""
    path = Path(log_path)
    is_new = not path.exists()
    when = when or datetime.now(timezone.utc).isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(
            {"date": when, "key": topic.key, "tool": topic.tool, "label": topic.label}
        )


def topic_by_key(key, pool=TOPIC_POOL):
    for topic in pool:
        if topic.key == key:
            return topic
    raise KeyError(f"등록되지 않은 토픽 key: {key}")
