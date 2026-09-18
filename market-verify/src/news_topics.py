"""어제 실제로 크게 움직인 자산에서 오늘의 소재를 고른다.

"어제 화제가 된 것"을 다루되, **뉴스 문장을 읽어서 고르지 않는다.** 뉴스 요약은
이 채널이 하지 않기로 한 것이고(NOTES.md), 모델이 기사 내용을 지어낼 여지도 있다.
대신 어제 종가가 얼마나 움직였는지를 코드가 직접 재서, 가장 크게 움직인 자산을
오늘의 대상으로 삼는다. 화제의 근거가 숫자라 검증이 가능하다.

고른 다음에 만드는 것은 여전히 에버그린 검증이다 — "어제 이런 일이 있었다"가
아니라 "이런 조건이 과거에 몇 번 있었고 그 뒤 분포가 어땠나". 소재만 어제에서
가져오고 형식은 그대로다.

움직임이 크지 않거나 데이터를 못 받으면 순환 풀(topics.py)로 돌아간다.
"어제 별일 없었는데 억지로 화제를 만드는" 것이 제일 나쁘다.
"""

from dataclasses import dataclass

from src.topics import Topic

# 감시 대상. 티커, 표기용 이름, 조건을 만들 때 쓸 시작일.
WATCHLIST = (
    ("^GSPC", "S&P 500", "1990-01-01"),
    ("^IXIC", "나스닥 종합", "1990-01-01"),
    ("^VIX", "VIX", "1990-01-01"),
    ("BTC-USD", "비트코인", "2015-01-01"),
    ("ETH-USD", "이더리움", "2017-01-01"),
    ("GC=F", "금", "2000-01-01"),
    ("KRW=X", "원달러 환율", "2003-12-01"),
)
# 이만큼은 움직여야 "어제 화제"로 친다. 이하면 순환 풀로 넘긴다.
MOVE_THRESHOLD_PCT = 1.5
# VIX 는 변동성 지수라 절대 수준이 의미를 갖는다.
VIX_LEVELS = (20.0, 30.0, 40.0)


@dataclass(frozen=True)
class Move:
    ticker: str
    label: str
    start: str
    change_pct: float
    last_close: float
    asof: str


def _last_change(close):
    """마지막 종가의 직전 대비 변화율(%)과 그 날짜."""
    if close is None or len(close) < 2:
        return None
    previous, last = float(close.iloc[-2]), float(close.iloc[-1])
    if previous == 0:
        return None
    return (last - previous) / previous * 100.0, last, str(close.index[-1].date())


def recent_moves(watchlist=WATCHLIST, fetch=None, log=print):
    """감시 대상의 최근 하루 변화율. 못 받은 종목은 건너뛴다."""
    if fetch is None:
        from src import market_events as me

        fetch = me.fetch_close

    moves = []
    for ticker, label, start in watchlist:
        try:
            close = fetch(ticker, "2020-01-01")
        except Exception as error:
            # 한 종목이 막혔다고 오늘 치를 통째로 버리지 않는다.
            log(f"  ! {ticker} 를 건너뛴다: {type(error).__name__}")
            continue
        measured = _last_change(close)
        if measured is None:
            continue
        change, last_close, asof = measured
        moves.append(Move(ticker, label, start, change, last_close, asof))
    return sorted(moves, key=lambda m: abs(m.change_pct), reverse=True)


def topic_for(move):
    """움직인 자산 하나를 에버그린 검증 토픽으로 바꾼다."""
    if move.ticker == "^VIX":
        # 지금 수준 바로 아래 기준선을 쓴다. "이 선을 넘었던 적들" 을 보는 것이다.
        level = max((lv for lv in VIX_LEVELS if lv <= move.last_close), default=VIX_LEVELS[0])
        return Topic(
            f"news-vix-{level:g}", "run",
            ("--ticker", "^VIX", "--condition", "threshold", "--level", f"{level:g}",
             "--start", move.start, "--label", move.label),
            f"VIX {level:g} 돌파 (어제 {move.change_pct:+.1f}%)",
        )

    if move.change_pct < 0:
        # 내렸다 — 전고점 대비 하락 구간을 본다. 이 채널이 가장 많이 쓰는 조건이다.
        pct = 20.0 if move.ticker in ("^GSPC", "^IXIC") else 30.0
        return Topic(
            f"news-{move.ticker}-drawdown{pct:g}", "run",
            ("--ticker", move.ticker, "--condition", "drawdown", "--pct", f"{pct:g}",
             "--start", move.start, "--label", move.label),
            f"{move.label} 고점 대비 {pct:g}% 하락 (어제 {move.change_pct:+.1f}%)",
        )

    # 올랐다 — 주간 연속 하락 뒤 흐름은 상승장에서도 자주 찾는 질문이다.
    return Topic(
        f"news-{move.ticker}-down3", "run",
        ("--ticker", move.ticker, "--condition", "down-weeks", "--n", "3",
         "--start", move.start, "--label", move.label),
        f"{move.label} 주간 3주 연속 하락 (어제 {move.change_pct:+.1f}%)",
    )


def topic_from_yesterday(
    watchlist=WATCHLIST, fetch=None, threshold=MOVE_THRESHOLD_PCT, used=(), log=print
):
    """어제 가장 크게 움직인 자산으로 토픽을 만든다. 없으면 None.

    이미 다룬 key 는 건너뛴다 — 같은 자산이 며칠 연속 흔들려도 같은 영상을
    두 번 만들지 않는다.
    """
    for move in recent_moves(watchlist, fetch, log):
        if abs(move.change_pct) < threshold:
            break  # 정렬돼 있으므로 뒤는 더 작다
        topic = topic_for(move)
        if topic.key in used:
            log(f"  · {move.label} 은 이미 다뤘다. 다음 후보를 본다.")
            continue
        log(f"어제 움직임: {move.label} {move.change_pct:+.2f}% ({move.asof} 종가 기준)")
        return topic
    return None
