"""매크로·유동성 지표가 어떤 상태였을 때 자산이 어떻게 움직였는지 본다.

상관계수를 내지 않는다. 상관은 인과로 읽히기 쉽고, 이 채널은 예측을 하지 않는다.
대신 조건 검증과 같은 방식을 쓴다 — "이 지표가 이 상태였던 시점이 과거에 몇 번
있었고, 그때 자산은 어떻게 됐나". 다른 점은 조건을 재는 시계열(FRED)과 결과를
재는 시계열(주가)이 다르다는 것뿐이다.
"""

import os

import pandas as pd

from src.market_events import (
    HORIZONS,
    MIN_SAMPLE_WARNING,
    apply_min_gap,
    block_header,
    forward_returns,
    summarize,
)

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_SOURCE = "FRED (Federal Reserve Bank of St. Louis)"
KEY_ENV = "FRED_API_KEY"

# 자주 쓰는 지표. 여기 없는 것도 FRED 시리즈 ID 로 그대로 넣을 수 있다.
KNOWN_SERIES = {
    "T10Y2Y": "장단기 금리차 (10년 - 2년)",
    "T10Y3M": "장단기 금리차 (10년 - 3개월)",
    "DGS10": "미국 10년 국채금리",
    "DFF": "연방기금금리",
    "M2SL": "M2 통화량",
    "WALCL": "연준 총자산",
    "RRPONTSYD": "역레포 잔액",
    "UNRATE": "실업률",
    "CPIAUCSL": "소비자물가지수",
    "DTWEXBGS": "달러지수 (광의)",
}


class FredError(RuntimeError):
    """FRED 에서 데이터를 받지 못했다."""


def series_name(series_id):
    return KNOWN_SERIES.get(series_id, series_id)


def check_api_key(env=None):
    """호출 전에 키를 본다. 문제가 없으면 None."""
    key = (os.environ if env is None else env).get(KEY_ENV, "")
    if not key:
        return (
            f"{KEY_ENV} 가 설정되지 않았다. fred.stlouisfed.org 에서 무료로 발급받아 "
            f"export {KEY_ENV}='...' 로 넣을 것."
        )
    if any(ch in key for ch in "\x1b\r\n\t "):
        return f"{KEY_ENV} 에 공백이나 제어문자가 섞여 있다. 다시 설정할 것."
    return None


def _default_fetcher(params):
    import requests

    response = requests.get(FRED_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_series(series_id, start, end=None, api_key=None, fetcher=None):
    """FRED 시계열 하나를 받는다. 결측(".")은 버린다."""
    key = api_key or os.environ.get(KEY_ENV, "")
    if not key:
        raise FredError(check_api_key({}))

    params = {
        "series_id": series_id,
        "api_key": key,
        "file_type": "json",
        "observation_start": start,
    }
    if end:
        params["observation_end"] = end

    payload = (fetcher or _default_fetcher)(params)
    observations = payload.get("observations") or []
    dates, values = [], []
    for row in observations:
        raw = row.get("value")
        if raw in (None, "", "."):
            continue
        dates.append(pd.Timestamp(row["date"]))
        values.append(float(raw))
    if not values:
        raise FredError(
            f"{series_id} 관측치를 받지 못했다. 시리즈 ID 와 기간을 확인할 것."
        )
    return pd.Series(values, index=pd.DatetimeIndex(dates)).sort_index()


def yoy_change(series, periods=12):
    """전년 대비 변화율(%). 월간 지표는 periods=12 가 1년이다."""
    if periods < 1:
        raise ValueError("periods 는 1 이상이어야 한다.")
    return (series / series.shift(periods) - 1.0).dropna() * 100.0


def cross_above(series, level):
    """값이 level 이상으로 처음 올라선 시점."""
    above = series >= level
    return list(series.index[above & ~above.shift(1, fill_value=False)])


def cross_below(series, level):
    """값이 level 이하로 처음 내려간 시점."""
    below = series <= level
    return list(series.index[below & ~below.shift(1, fill_value=False)])


def to_trading_days(dates, close):
    """지표 발표일을 자산의 거래일로 옮긴다.

    지표는 월간·주간이고 발표일이 휴장일일 수도 있다. 그 날짜로 바로 수익률을
    계산하면 없는 가격을 참조하게 되므로, 그 이후 첫 거래일로 민다.
    """
    index = close.index
    mapped = []
    for date in sorted(dates):
        position = index.searchsorted(pd.Timestamp(date), side="left")
        if position < len(index):
            mapped.append(index[position])
    # 여러 지표일이 같은 거래일로 몰릴 수 있다. 중복을 없애고 순서를 지킨다.
    seen = set()
    return [d for d in mapped if not (d in seen or seen.add(d))]


def to_block(series_id, ticker, condition, rows, summary, macro_start, macro_end,
             price_start, price_end, asof, label=None, stream=None):
    """대본 작성자에게 넘길 데이터 블록."""
    import sys

    stream = sys.stderr if stream is None else stream
    if len(rows) < MIN_SAMPLE_WARNING:
        print(
            f"[경고] 사례가 {len(rows)}건이다. {MIN_SAMPLE_WARNING}건 미만은 "
            "경향이 아니라 우연이므로 대본으로 만들지 않는 편이 낫다.",
            file=stream,
        )

    header_cells = " | ".join(f"{h}거래일({name})" for h, name in HORIZONS)
    lines = block_header(
        ticker,
        condition,
        price_start,
        price_end,
        asof,
        len(rows),
        label=label,
        source=f"{FRED_SOURCE} / Yahoo Finance",
        extra_lines=[
            f"지표: {series_id} ({series_name(series_id)})",
            f"지표 기간: {macro_start} ~ {macro_end}",
        ],
    )
    lines += [
        "",
        "[사례별 이후 수익률 %]",
        f"| 발생일 | {header_cells} |",
        "| --- " * (len(HORIZONS) + 1) + "|",
    ]
    for row in rows:
        cells = " | ".join(
            "데이터 부족" if row["returns"][h] is None else f"{row['returns'][h]:.2f}"
            for h, _ in HORIZONS
        )
        lines.append(f"| {row['date']:%Y-%m-%d} | {cells} |")

    lines += [
        "",
        "[분포 요약]",
        "| 구간 | 표본수 | 중앙값 | 평균 | 최저 | 최고 | 상승비율 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for horizon, name in HORIZONS:
        stat = summary.get(horizon)
        cell = f"{horizon}거래일({name})"
        if stat is None:
            lines.append(f"| {cell} | 데이터 부족 | | | | | |")
            continue
        lines.append(
            f"| {cell} | {stat['count']} | {stat['median']:.2f} | {stat['mean']:.2f} "
            f"| {stat['min']:.2f} | {stat['max']:.2f} | {stat['positive_ratio']:.2f} |"
        )

    lines += ["", "=== 블록 끝 ==="]
    return "\n".join(lines) + "\n"


def build_block(macro, close, series_id, ticker, condition, event_dates, asof, label=None):
    """지표 조건 시점을 받아 간격 필터부터 블록 생성까지 처리한다."""
    trading_days = to_trading_days(event_dates, close)
    kept = apply_min_gap(trading_days, close)
    rows = forward_returns(close, kept)
    summary = summarize(rows)
    block = to_block(
        series_id=series_id,
        ticker=ticker,
        condition=condition,
        rows=rows,
        summary=summary,
        macro_start=f"{macro.index[0]:%Y-%m-%d}",
        macro_end=f"{macro.index[-1]:%Y-%m-%d}",
        price_start=f"{close.index[0]:%Y-%m-%d}",
        price_end=f"{close.index[-1]:%Y-%m-%d}",
        asof=asof,
        label=label,
    )
    return block, rows, summary
