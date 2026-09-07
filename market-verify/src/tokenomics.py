"""토크노믹스 해부 — 공급이 어떤 규칙으로 늘고, 그동안 무엇이 달라졌나.

두 갈래로 본다.

1. **발행 스케줄** — 비트코인식 반감기 공급 곡선은 합의 규칙이라 결정론적이다.
   누가 발표하는 수치가 아니므로 외부 데이터 없이 계산한다. 여기에는 추정이
   들어갈 자리가 없다.
2. **실측 희석률** — 유통량은 코인마다 규칙이 다르고 공시도 제각각이다.
   시가총액 ÷ 가격으로 유도해 증가율을 본다.

가격을 예측하지 않는다. 공급이 어떻게 늘었는지와, 그 구간에 가격이 어땠는지를
나란히 놓을 뿐이다.
"""

import sys

import pandas as pd

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
COINGECKO_SOURCE = "CoinGecko"
SCHEDULE_SOURCE = "합의 규칙에서 계산 (외부 데이터 없음)"

# 비트코인 합의 규칙. 코드에 박힌 값이지 누가 정하는 수치가 아니다.
HALVING_INTERVAL_BLOCKS = 210_000
INITIAL_BLOCK_REWARD = 50.0
TARGET_BLOCK_MINUTES = 10
MINUTES_PER_YEAR = 365.25 * 24 * 60

# 실제로 기록된 반감기 날짜. 미래 반감기는 10분 블록 가정으로 추정한다.
# 정확한 날짜가 필요하면 블록 탐색기에서 확인해 이 표를 고친다.
RECORDED_HALVINGS = {
    0: "2009-01-03",
    1: "2012-11-28",
    2: "2016-07-09",
    3: "2020-05-11",
    4: "2024-04-20",
}


class TokenomicsError(RuntimeError):
    """공급 데이터를 만들지 못했다."""


def epoch_years():
    """한 반감기 구간의 길이(년). 블록 목표 시간에서 나온다."""
    return HALVING_INTERVAL_BLOCKS * TARGET_BLOCK_MINUTES / MINUTES_PER_YEAR


def halving_schedule(epochs=8):
    """반감기 구간별 발행량·누적 공급·연 환산 인플레이션율.

    구간 시작 시점의 인플레이션율로 적는다 — 그 구간에 새로 풀리는 양을
    그때까지 쌓인 공급으로 나눈 값이다.
    """
    if epochs < 1:
        raise ValueError("epochs 는 1 이상이어야 한다.")

    years = epoch_years()
    rows = []
    cumulative = 0.0
    for epoch in range(epochs):
        reward = INITIAL_BLOCK_REWARD / (2**epoch)
        issued = HALVING_INTERVAL_BLOCKS * reward
        annual = issued / years
        rows.append(
            {
                "epoch": epoch,
                "start_block": epoch * HALVING_INTERVAL_BLOCKS,
                "reward": reward,
                "issued": issued,
                "supply_before": cumulative,
                "supply_after": cumulative + issued,
                # 첫 구간은 이전 공급이 0이라 비율을 낼 수 없다.
                "annual_inflation": (annual / cumulative * 100.0) if cumulative else None,
                "date": RECORDED_HALVINGS.get(epoch),
                "estimated": epoch not in RECORDED_HALVINGS,
            }
        )
        cumulative += issued
    return rows


def terminal_supply(epochs=64):
    """스케줄이 수렴하는 총 발행량."""
    return sum(row["issued"] for row in halving_schedule(epochs))


def _default_fetcher(coin_id, params):
    import requests

    response = requests.get(
        COINGECKO_URL.format(coin_id=coin_id), params=params, timeout=30
    )
    response.raise_for_status()
    return response.json()


def fetch_market_chart(coin_id, days="max", fetcher=None):
    """가격과 시가총액 시계열을 받는다. (price, market_cap)"""
    payload = (fetcher or _default_fetcher)(
        coin_id, {"vs_currency": "usd", "days": days, "interval": "daily"}
    )
    prices = payload.get("prices") or []
    caps = payload.get("market_caps") or []
    if not prices or not caps:
        raise TokenomicsError(
            f"{coin_id} 시계열을 받지 못했다. 코인 ID 를 확인할 것 (예: bitcoin, ethereum)."
        )

    def to_series(pairs):
        index = pd.to_datetime([int(ms) for ms, _ in pairs], unit="ms").normalize()
        return pd.Series([float(v) for _, v in pairs], index=index)

    price = to_series(prices)
    cap = to_series(caps)
    frame = pd.concat([price, cap], axis=1, join="inner").dropna()
    return frame.iloc[:, 0], frame.iloc[:, 1]


def implied_supply(price, market_cap):
    """유통량 = 시가총액 ÷ 가격.

    코인마다 유통량 공시 기준이 다르고 시점도 어긋난다. 시총과 가격은 같은
    스냅샷에서 나오므로 이렇게 유도하는 편이 두 값을 따로 받는 것보다 어긋나지 않는다.
    """
    if (price <= 0).any():
        raise TokenomicsError("가격에 0 이하가 있어 유통량을 유도할 수 없다.")
    return (market_cap / price).dropna()


def supply_growth(supply, periods=365):
    """공급 증가율(%). 일간 시계열이면 periods=365 가 1년이다."""
    if periods < 1:
        raise ValueError("periods 는 1 이상이어야 한다.")
    return ((supply / supply.shift(periods) - 1.0).dropna() * 100.0)


def _fmt_amount(value):
    return f"{value:,.2f}"


def to_schedule_block(asset, rows, asof, total_supply, stream=None):
    """발행 스케줄 블록. 외부 데이터가 없으므로 경고할 표본 수도 없다."""
    stream = sys.stderr if stream is None else stream
    estimated = [row for row in rows if row["estimated"]]
    if estimated:
        print(
            f"[참고] 구간 {len(estimated)}개는 날짜가 추정치다. "
            "블록에도 추정으로 표기했다.",
            file=stream,
        )

    lines = [
        "=== 데이터 블록 (이 안의 수치만 사용) ===",
        f"대상: {asset}",
        f"발행 규칙: {HALVING_INTERVAL_BLOCKS:,}블록마다 보상 절반, "
        f"최초 보상 {INITIAL_BLOCK_REWARD:g}, 목표 블록 간격 {TARGET_BLOCK_MINUTES}분",
        f"구간 길이: 약 {epoch_years():.2f}년",
        f"수렴 총 발행량: {_fmt_amount(total_supply)}",
        f"출처: {SCHEDULE_SOURCE}",
        f"조회일: {asof}",
        f"구간 수: {len(rows)}",
        "",
        "[반감기 구간별 발행]",
        "| 구간 | 시작 블록 | 시작일 | 블록 보상 | 구간 발행량 | 구간 종료 누적 | 연 환산 인플레이션 % |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        date = row["date"] or "미도래"
        if row["estimated"] and row["date"]:
            date = f"{row['date']} (추정)"
        inflation = (
            "해당 없음"
            if row["annual_inflation"] is None
            else f"{row['annual_inflation']:.2f}"
        )
        lines.append(
            f"| {row['epoch']} | {row['start_block']:,} | {date} | {row['reward']:g} "
            f"| {_fmt_amount(row['issued'])} | {_fmt_amount(row['supply_after'])} "
            f"| {inflation} |"
        )

    lines += ["", "=== 블록 끝 ==="]
    return "\n".join(lines) + "\n"


def to_dilution_block(coin_id, asset, samples, asof, stream=None):
    """실측 희석률 블록. samples 는 (날짜, 유통량, 증가율, 가격) 목록."""
    stream = sys.stderr if stream is None else stream
    if len(samples) < 3:
        print(
            f"[경고] 관측 구간이 {len(samples)}개다. 이 수로는 경향을 말할 수 없다.",
            file=stream,
        )

    lines = [
        "=== 데이터 블록 (이 안의 수치만 사용) ===",
        f"대상: {asset}",
        f"코인 ID: {coin_id}",
        "유통량 산출: 시가총액 ÷ 가격",
        f"출처: {COINGECKO_SOURCE}",
        f"조회일: {asof}",
        f"관측 구간 수: {len(samples)}",
        "",
        "[연도별 유통량과 전년 대비 증가율]",
        "| 기준일 | 유통량 | 전년 대비 증가율 % | 가격 USD |",
        "| --- | --- | --- | --- |",
    ]
    for sample in samples:
        lines.append(
            f"| {sample['date']:%Y-%m-%d} | {_fmt_amount(sample['supply'])} "
            f"| {sample['growth']:.2f} | {sample['price']:,.2f} |"
        )
    lines += ["", "=== 블록 끝 ==="]
    return "\n".join(lines) + "\n"


def yearly_samples(price, supply, growth, per_year=365):
    """연 단위로 한 점씩 뽑는다. 매일 찍으면 표가 수천 줄이 된다."""
    samples = []
    dates = list(growth.index)
    for position in range(0, len(dates), per_year):
        date = dates[position]
        samples.append(
            {
                "date": date,
                "supply": float(supply[date]),
                "growth": float(growth[date]),
                "price": float(price[date]),
            }
        )
    return samples


def build_schedule_block(asset, asof, epochs=8):
    rows = halving_schedule(epochs)
    block = to_schedule_block(asset, rows, asof, terminal_supply())
    return block, rows


def build_dilution_block(coin_id, asset, price, market_cap, asof, periods=365):
    supply = implied_supply(price, market_cap)
    growth = supply_growth(supply, periods)
    if growth.empty:
        raise TokenomicsError(
            f"{coin_id} 기록이 {periods}일보다 짧아 증가율을 낼 수 없다."
        )
    samples = yearly_samples(price, supply, growth, periods)
    block = to_dilution_block(coin_id, asset, samples, asof)
    return block, samples
