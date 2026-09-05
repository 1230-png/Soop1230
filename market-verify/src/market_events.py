"""과거 사례를 코드로 뽑아내고 대본용 데이터 블록을 만든다.

LLM은 시계열 수치를 지어낸다. 그래서 숫자는 전부 여기서 나오고,
대본 작성자는 to_block()이 만든 텍스트 안의 숫자만 쓸 수 있다.
"""

import sys

import pandas as pd

HORIZONS = [(21, "1개월"), (126, "6개월"), (252, "12개월")]
MIN_GAP_TRADING_DAYS = 60
MIN_SAMPLE_WARNING = 5
SOURCE = "Yahoo Finance"

# 대본이 구조상 쓸 수밖에 없는 숫자(섹션 번호, 컷 번호, 초 단위).
# 블록에 명시해 두지 않으면 검증기가 전부 환각으로 잡는다.
STRUCTURE_NUMBERS = [1, 2, 3, 4, 5, 6, 7, 12, 60]


def fetch_close(ticker, start, end=None):
    """일별 수정종가 시계열을 돌려준다."""
    import yfinance as yf

    df = yf.download(
        ticker, start=start, end=end, auto_adjust=True, progress=False, actions=False
    )
    if df is None or len(df) == 0:
        raise ValueError(
            f"{ticker} 데이터를 받지 못했다. 티커·기간과 네트워크 연결을 확인할 것."
        )
    return _extract_close(df)


def _extract_close(df):
    """yfinance가 MultiIndex 컬럼으로 줄 때와 아닐 때를 모두 받는다."""
    if isinstance(df.columns, pd.MultiIndex):
        levels = [df.columns.get_level_values(i) for i in range(df.columns.nlevels)]
        for level, values in enumerate(levels):
            if "Close" in values:
                close = df.xs("Close", axis=1, level=level)
                break
        else:
            raise ValueError("Close 컬럼을 찾지 못했다.")
    else:
        close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna()
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.astype(float)


def down_weeks(close, n=3):
    """주간 종가가 n주 연속 하락한 시점."""
    if n < 1:
        raise ValueError("n은 1 이상이어야 한다.")
    weekly = close.resample("W-FRI").last().dropna()
    last_trading_day = (
        pd.Series(close.index, index=close.index).resample("W-FRI").last().dropna()
    )
    falling = (weekly.diff() < 0).astype(float)
    streak = falling.rolling(n).sum()
    hit_weeks = weekly.index[streak.eq(n).fillna(False)]
    return [last_trading_day[week] for week in hit_weeks if week in last_trading_day]


def drawdown_entry(close, pct=10.0):
    """전고점 대비 -pct% 구간에 처음 들어선 시점."""
    if pct <= 0:
        raise ValueError("pct는 0보다 커야 한다.")
    drawdown = close / close.cummax() - 1.0
    below = drawdown <= -abs(pct) / 100.0
    entered = below & ~below.shift(1, fill_value=False)
    return list(close.index[entered])


def threshold_break(series, level):
    """시계열이 level 이상으로 처음 올라선 시점 (VIX 등)."""
    series = series.dropna()
    above = series >= level
    entered = above & ~above.shift(1, fill_value=False)
    return list(series.index[entered])


def apply_min_gap(dates, close, min_gap=MIN_GAP_TRADING_DAYS):
    """사례 간 최소 거래일 간격을 강제한다.

    이 필터가 없으면 한 번의 하락장이 사례 수십 건으로 부풀어
    대본이 "과거에 20번 있었다"는 거짓말을 하게 된다.
    """
    positions = {date: pos for pos, date in enumerate(close.index)}
    kept = []
    last_pos = None
    for date in sorted(dates):
        pos = positions.get(date)
        if pos is None:
            continue
        if last_pos is not None and pos - last_pos < min_gap:
            continue
        kept.append(date)
        last_pos = pos
    return kept


def forward_returns(close, dates):
    """각 사례 이후 21/126/252 거래일 수익률(%). 데이터가 모자라면 None."""
    positions = {date: pos for pos, date in enumerate(close.index)}
    values = close.to_numpy()
    rows = []
    for date in dates:
        pos = positions[date]
        entry = {"date": date, "returns": {}}
        for horizon, _ in HORIZONS:
            target = pos + horizon
            if target < len(values):
                entry["returns"][horizon] = (values[target] / values[pos] - 1.0) * 100.0
            else:
                entry["returns"][horizon] = None
        rows.append(entry)
    return rows


def summarize(rows):
    """구간별 분포. 평균만 내면 -30%와 +50%가 +10%로 보인다."""
    summary = {}
    for horizon, _ in HORIZONS:
        values = [
            r["returns"][horizon] for r in rows if r["returns"][horizon] is not None
        ]
        if not values:
            summary[horizon] = None
            continue
        series = pd.Series(values)
        summary[horizon] = {
            "count": len(values),
            "median": float(series.median()),
            "mean": float(series.mean()),
            "min": float(series.min()),
            "max": float(series.max()),
            "positive_ratio": float((series > 0).sum()) / len(values) * 100.0,
        }
    return summary


def _fmt(value):
    return "데이터 부족" if value is None else f"{value:.2f}"


def to_block(
    ticker,
    condition,
    rows,
    summary,
    data_start,
    data_end,
    asof,
    label=None,
    source=SOURCE,
    stream=None,
):
    """대본 작성자에게 넘길 데이터 블록 텍스트."""
    # sys.stderr는 호출 시점에 잡는다. 기본 인자로 굳히면 테스트가 가로채지 못한다.
    stream = sys.stderr if stream is None else stream
    if len(rows) < MIN_SAMPLE_WARNING:
        print(
            f"[경고] 사례가 {len(rows)}건이다. {MIN_SAMPLE_WARNING}건 미만은 "
            "경향이 아니라 우연이므로 대본으로 만들지 않는 편이 낫다.",
            file=stream,
        )

    target = f"{ticker} ({label})" if label else ticker
    header_cells = " | ".join(f"{h}거래일({name})" for h, name in HORIZONS)
    lines = [
        "=== 데이터 블록 (이 안의 수치만 사용) ===",
        f"대상: {target}",
        f"조건: {condition}",
        f"데이터 기간: {data_start} ~ {data_end}",
        f"출처: {source}",
        f"조회일: {asof}",
        "주가 기준: 수정주가",
        f"사례 수: {len(rows)}",
        "",
        "[사례별 이후 수익률 %]",
        f"| 발생일 | {header_cells} |",
        "| --- " * (len(HORIZONS) + 1) + "|",
    ]
    for row in rows:
        cells = " | ".join(_fmt(row["returns"][h]) for h, _ in HORIZONS)
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

    lines += [
        "",
        "[대본 구조용 허용 숫자]",
        " ".join(str(n) for n in STRUCTURE_NUMBERS),
        "",
        "=== 블록 끝 ===",
    ]
    return "\n".join(lines) + "\n"


def build_block(close, dates, ticker, condition, asof, label=None):
    """조건 시점 목록을 받아 간격 필터부터 블록 생성까지 한 번에 처리한다."""
    kept = apply_min_gap(dates, close)
    rows = forward_returns(close, kept)
    summary = summarize(rows)
    block = to_block(
        ticker=ticker,
        condition=condition,
        rows=rows,
        summary=summary,
        data_start=f"{close.index[0]:%Y-%m-%d}",
        data_end=f"{close.index[-1]:%Y-%m-%d}",
        asof=pd.Timestamp.today().strftime("%Y-%m-%d") if asof is None else asof,
        label=label,
    )
    return block, rows, summary
