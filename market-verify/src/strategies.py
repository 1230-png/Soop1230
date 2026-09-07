"""수학적 투자 전략의 메커니즘을 과거 데이터로 검증한다.

"분할 매수가 유리하다"는 말을 믿거나 반박하지 않는다. 같은 돈을 같은 기간
넣었을 때 실제로 무엇이 달랐는지만 수치로 낸다. 결론은 시청자가 낸다.

조건 검증(market_events)과 다른 점: 사건이 언제 있었나가 아니라,
같은 시점에 두 방식을 나란히 굴리면 결과가 어떻게 갈리나를 본다.
"""

import sys

import pandas as pd

from src.market_events import (
    MIN_SAMPLE_WARNING,
    SOURCE,
    block_header,
    distribution,
)

# 한 달을 거래일로 근사한다. 실제 달마다 다르지만 시뮬레이션 기준을 하나로 둔다.
MONTH_DAYS = 21
# 시작 시점 간 최소 간격. 창이 겹치면 같은 국면이 표본 수십 개로 부풀어
# "과거 200번 중" 같은 거짓말이 된다. 조건 검증의 60거래일 필터와 같은 이유다.
DEFAULT_START_GAP = 126


def _sample_starts(close, span_days, gap):
    """끝까지 굴릴 수 있고 서로 겹치지 않는 시작 위치를 고른다."""
    last = len(close) - span_days - 1
    if last < 0:
        return []
    return list(range(0, last + 1, max(gap, 1)))


def dca_vs_lumpsum(close, contrib_months=12, hold_months=36, gap=DEFAULT_START_GAP):
    """같은 금액을 일시에 넣은 경우와 나눠 넣은 경우를 같은 시점에 비교한다.

    두 방식 모두 같은 날 끝난다. 끝나는 날이 다르면 비교가 성립하지 않는다.
    분할 매수는 매달 1/contrib_months 씩 넣고, 남은 기간은 그대로 들고 간다.
    """
    if contrib_months < 1:
        raise ValueError("contrib_months 는 1 이상이어야 한다.")
    if hold_months < contrib_months:
        raise ValueError("보유 기간이 납입 기간보다 짧을 수 없다.")

    span = hold_months * MONTH_DAYS
    prices = close.to_numpy()
    rows = []
    for start in _sample_starts(close, span, gap):
        end = start + span
        end_price = prices[end]

        lump_units = 1.0 / prices[start]
        lump = (lump_units * end_price - 1.0) * 100.0

        slice_amount = 1.0 / contrib_months
        dca_units = sum(
            slice_amount / prices[start + month * MONTH_DAYS]
            for month in range(contrib_months)
        )
        dca = (dca_units * end_price - 1.0) * 100.0

        rows.append(
            {
                "date": close.index[start],
                "lump": lump,
                "dca": dca,
                "gap": dca - lump,
            }
        )
    return rows


def compare(rows):
    """두 방식의 분포와, 분할 매수가 앞선 비율."""
    total = len(rows)
    dca_wins = sum(1 for row in rows if row["gap"] > 0)
    return {
        "lump": distribution([row["lump"] for row in rows]),
        "dca": distribution([row["dca"] for row in rows]),
        "gap": distribution([row["gap"] for row in rows]),
        "dca_win_ratio": (dca_wins / total * 100.0) if total else None,
        "dca_wins": dca_wins,
        "count": total,
    }


def _fmt(value):
    return "데이터 부족" if value is None else f"{value:.2f}"


def _distribution_row(label, stat):
    if stat is None:
        return f"| {label} | 데이터 부족 | | | | | |"
    return (
        f"| {label} | {stat['count']} | {stat['median']:.2f} | {stat['mean']:.2f} "
        f"| {stat['min']:.2f} | {stat['max']:.2f} | {stat['positive_ratio']:.2f} |"
    )


def to_dca_block(ticker, rows, result, contrib_months, hold_months,
             data_start, data_end, asof, label=None, source=SOURCE, stream=None):
    """대본 작성자에게 넘길 데이터 블록."""
    stream = sys.stderr if stream is None else stream
    if len(rows) < MIN_SAMPLE_WARNING:
        print(
            f"[경고] 시작 시점이 {len(rows)}개다. {MIN_SAMPLE_WARNING}개 미만은 "
            "경향이 아니라 우연이므로 대본으로 만들지 않는 편이 낫다.",
            file=stream,
        )

    strategy = (
        f"{contrib_months}개월 분할 매수와 일시 매수를 같은 날 시작해 "
        f"{hold_months}개월 뒤 함께 청산"
    )
    lines = block_header(
        ticker, strategy, data_start, data_end, asof, len(rows),
        label=label, source=source, condition_label="전략", count_label="시작 시점 수",
    )

    lines += [
        "",
        "[시작 시점별 최종 수익률 %]",
        "| 시작일 | 일시 매수 | 분할 매수 | 차이(분할-일시) |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['date']:%Y-%m-%d} | {row['lump']:.2f} | "
            f"{row['dca']:.2f} | {row['gap']:.2f} |"
        )

    lines += [
        "",
        "[분포 요약]",
        "| 항목 | 표본수 | 중앙값 | 평균 | 최저 | 최고 | 0보다 큰 비율 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        _distribution_row("일시 매수 수익률", result["lump"]),
        _distribution_row("분할 매수 수익률", result["dca"]),
        _distribution_row("차이(분할-일시)", result["gap"]),
        "",
        "[분할 매수가 앞선 횟수]",
        f"| 앞선 시점 | 전체 시점 | 비율 |",
        "| --- | --- | --- |",
        f"| {result['dca_wins']} | {result['count']} | {_fmt(result['dca_win_ratio'])} |",
        "",
        "=== 블록 끝 ===",
    ]
    return "\n".join(lines) + "\n"


def build_dca_block(close, ticker, contrib_months, hold_months, asof,
                label=None, gap=DEFAULT_START_GAP):
    """시뮬레이션부터 블록 생성까지 한 번에."""
    rows = dca_vs_lumpsum(close, contrib_months, hold_months, gap)
    result = compare(rows)
    block = to_dca_block(
        ticker=ticker,
        rows=rows,
        result=result,
        contrib_months=contrib_months,
        hold_months=hold_months,
        data_start=f"{close.index[0]:%Y-%m-%d}",
        data_end=f"{close.index[-1]:%Y-%m-%d}",
        asof=asof,
        label=label,
    )
    return block, rows, result


# ─── 리밸런싱 주기 검증 ───────────────────────────────────────────────
#
# 리밸런싱은 수익을 늘리려는 장치가 아니라 비중이 한쪽으로 쏠리는 것을 막는
# 장치다. 그래서 최종 수익률만 비교하면 요점을 놓친다. 최대 낙폭을 함께 낸다.

NO_REBALANCE = 0
DEFAULT_INTERVALS = (NO_REBALANCE, 3, 12)


def align(close_a, close_b):
    """두 시계열을 공통 거래일로 맞춘다.

    상장일도 휴장일도 다르다. 맞추지 않으면 없는 날 가격으로 계산하게 된다.
    """
    frame = pd.concat([close_a, close_b], axis=1, join="inner").dropna()
    return frame.iloc[:, 0], frame.iloc[:, 1]


def interval_label(months):
    return "리밸런싱 없음" if months == NO_REBALANCE else f"{months}개월"


def simulate_rebalance(prices_a, prices_b, weight_a, interval_months, start, span):
    """한 시작 시점에서 굴린 결과. (최종 수익률 %, 최대 낙폭 %)"""
    units_a = weight_a / prices_a[start]
    units_b = (1.0 - weight_a) / prices_b[start]
    step = interval_months * MONTH_DAYS

    peak = 1.0
    worst = 0.0
    value = 1.0
    for offset in range(span + 1):
        position = start + offset
        value = units_a * prices_a[position] + units_b * prices_b[position]
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0)
        if step and offset and offset % step == 0:
            units_a = weight_a * value / prices_a[position]
            units_b = (1.0 - weight_a) * value / prices_b[position]

    return (value - 1.0) * 100.0, worst * 100.0


def rebalance_intervals(close_a, close_b, weight_a=0.6, hold_months=60,
                        intervals=DEFAULT_INTERVALS, gap=DEFAULT_START_GAP):
    """같은 시작 시점에서 주기만 바꿔 굴린다."""
    if not 0.0 < weight_a < 1.0:
        raise ValueError("weight_a 는 0 과 1 사이여야 한다.")
    for months in intervals:
        if months < 0:
            raise ValueError("리밸런싱 주기는 0 이상이어야 한다.")
        if months > hold_months:
            raise ValueError(f"주기({months}개월)가 보유 기간({hold_months}개월)보다 길다.")

    prices_a, prices_b = align(close_a, close_b)
    span = hold_months * MONTH_DAYS
    array_a = prices_a.to_numpy()
    array_b = prices_b.to_numpy()

    rows = []
    for start in _sample_starts(prices_a, span, gap):
        entry = {"date": prices_a.index[start], "returns": {}, "drawdowns": {}}
        for months in intervals:
            total, worst = simulate_rebalance(
                array_a, array_b, weight_a, months, start, span
            )
            entry["returns"][months] = total
            entry["drawdowns"][months] = worst
        rows.append(entry)
    return rows


def compare_intervals(rows, intervals=DEFAULT_INTERVALS):
    """주기별 최종 수익률과 최대 낙폭의 분포."""
    return {
        months: {
            "return": distribution([row["returns"][months] for row in rows]),
            "drawdown": distribution([row["drawdowns"][months] for row in rows]),
        }
        for months in intervals
    }


def to_rebalance_block(ticker_a, ticker_b, rows, result, weight_a, hold_months,
                       intervals, data_start, data_end, asof,
                       label_a=None, label_b=None, source=SOURCE, stream=None):
    """리밸런싱 검증 데이터 블록."""
    stream = sys.stderr if stream is None else stream
    if len(rows) < MIN_SAMPLE_WARNING:
        print(
            f"[경고] 시작 시점이 {len(rows)}개다. {MIN_SAMPLE_WARNING}개 미만은 "
            "경향이 아니라 우연이므로 대본으로 만들지 않는 편이 낫다.",
            file=stream,
        )

    percent_a = round(weight_a * 100)
    name_a = f"{ticker_a} ({label_a})" if label_a else ticker_a
    name_b = f"{ticker_b} ({label_b})" if label_b else ticker_b
    # 종목명은 대상 줄에만 둔다. 전략 줄에서 되풀이하면 읽기 나쁘다.
    strategy = (
        f"{percent_a} 대 {100 - percent_a} 비중을 {hold_months}개월 보유하며 "
        "리밸런싱 주기만 바꿔 비교"
    )
    lines = block_header(
        f"{name_a} + {name_b}", strategy, data_start, data_end, asof, len(rows),
        source=source, condition_label="전략", count_label="시작 시점 수",
    )

    labels = [interval_label(months) for months in intervals]
    lines += [
        "",
        "[시작 시점별 최종 수익률 %]",
        "| 시작일 | " + " | ".join(labels) + " |",
        "| --- " * (len(intervals) + 1) + "|",
    ]
    for row in rows:
        cells = " | ".join(f"{row['returns'][m]:.2f}" for m in intervals)
        lines.append(f"| {row['date']:%Y-%m-%d} | {cells} |")

    lines += [
        "",
        "[분포 요약 — 최종 수익률 %]",
        "| 주기 | 표본수 | 중앙값 | 평균 | 최저 | 최고 | 0보다 큰 비율 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for months in intervals:
        lines.append(
            _distribution_row(interval_label(months), result[months]["return"])
        )

    lines += [
        "",
        "[분포 요약 — 최대 낙폭 %]",
        "| 주기 | 표본수 | 중앙값 | 평균 | 가장 깊은 낙폭 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for months in intervals:
        stat = result[months]["drawdown"]
        if stat is None:
            lines.append(f"| {interval_label(months)} | 데이터 부족 | | | |")
            continue
        lines.append(
            f"| {interval_label(months)} | {stat['count']} | {stat['median']:.2f} "
            f"| {stat['mean']:.2f} | {stat['min']:.2f} |"
        )

    lines += ["", "=== 블록 끝 ==="]
    return "\n".join(lines) + "\n"


def build_rebalance_block(close_a, close_b, ticker_a, ticker_b, asof,
                          weight_a=0.6, hold_months=60, intervals=DEFAULT_INTERVALS,
                          label_a=None, label_b=None, gap=DEFAULT_START_GAP):
    rows = rebalance_intervals(close_a, close_b, weight_a, hold_months, intervals, gap)
    result = compare_intervals(rows, intervals)
    aligned_a, _ = align(close_a, close_b)
    block = to_rebalance_block(
        ticker_a=ticker_a,
        ticker_b=ticker_b,
        rows=rows,
        result=result,
        weight_a=weight_a,
        hold_months=hold_months,
        intervals=intervals,
        data_start=f"{aligned_a.index[0]:%Y-%m-%d}",
        data_end=f"{aligned_a.index[-1]:%Y-%m-%d}",
        asof=asof,
        label_a=label_a,
        label_b=label_b,
    )
    return block, rows, result
