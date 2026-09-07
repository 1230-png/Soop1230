import io

import pandas as pd
import pytest

from src import strategies
from src.strategies import MONTH_DAYS, build_dca_block, compare, dca_vs_lumpsum, to_dca_block
from src.validator import validate


def series(values, start="2000-01-03"):
    return pd.Series(
        [float(v) for v in values], index=pd.bdate_range(start=start, periods=len(values))
    )


def flat(months=40, price=100.0):
    return series([price] * (months * MONTH_DAYS))


def rising(months=40, step=0.1):
    return series([100 + i * step for i in range(months * MONTH_DAYS)])


def dip_then_recover(months=40, contrib=12, step=0.15):
    down = [100 - i * step for i in range(contrib * MONTH_DAYS)]
    up = [down[-1] + i * step for i in range(months * MONTH_DAYS - len(down))]
    return series(down + up)


def test_flat_market_returns_nothing_either_way():
    row = dca_vs_lumpsum(flat(), 12, 36)[0]
    assert row["lump"] == pytest.approx(0.0, abs=1e-9)
    assert row["dca"] == pytest.approx(0.0, abs=1e-9)
    assert row["gap"] == pytest.approx(0.0, abs=1e-9)


def test_rising_market_favours_lump_sum():
    """계속 오르면 먼저 들어가 있는 쪽이 앞선다."""
    row = dca_vs_lumpsum(rising(), 12, 36)[0]
    assert row["lump"] > row["dca"]
    assert row["gap"] < 0


def test_dip_then_recovery_favours_dca():
    """먼저 빠지면 같은 돈으로 더 많이 산다."""
    row = dca_vs_lumpsum(dip_then_recover(), 12, 36)[0]
    assert row["dca"] > row["lump"]
    assert row["gap"] > 0


def test_both_strategies_end_on_the_same_day():
    """끝나는 날이 다르면 비교가 성립하지 않는다."""
    close = rising()
    rows = dca_vs_lumpsum(close, 12, 36)
    span = 36 * MONTH_DAYS
    for row in rows:
        start = list(close.index).index(row["date"])
        assert start + span < len(close)


def test_gap_is_the_difference_of_the_two():
    for row in dca_vs_lumpsum(dip_then_recover(), 6, 24):
        assert row["gap"] == pytest.approx(row["dca"] - row["lump"])


def test_single_month_contribution_equals_lump_sum():
    """한 번에 다 넣는 분할 매수는 일시 매수와 같아야 한다."""
    row = dca_vs_lumpsum(rising(), contrib_months=1, hold_months=36)[0]
    assert row["dca"] == pytest.approx(row["lump"])


def test_start_points_do_not_overlap():
    """창이 겹치면 같은 국면이 표본 수십 개로 부풀어 대본이 거짓말을 한다."""
    close = rising(months=120)
    rows = dca_vs_lumpsum(close, 12, 36, gap=126)
    positions = [list(close.index).index(r["date"]) for r in rows]
    assert all(b - a >= 126 for a, b in zip(positions, positions[1:]))


def test_wider_gap_yields_fewer_start_points():
    close = rising(months=120)
    assert len(dca_vs_lumpsum(close, 12, 36, gap=252)) < len(
        dca_vs_lumpsum(close, 12, 36, gap=63)
    )


def test_short_history_yields_no_rows():
    assert dca_vs_lumpsum(series([100.0] * 50), 12, 36) == []


def test_rejects_impossible_settings():
    with pytest.raises(ValueError):
        dca_vs_lumpsum(rising(), contrib_months=0, hold_months=36)
    with pytest.raises(ValueError):
        dca_vs_lumpsum(rising(), contrib_months=24, hold_months=12)


def test_compare_reports_both_distributions_and_the_win_ratio():
    result = compare(dca_vs_lumpsum(rising(months=120), 12, 36))
    assert result["lump"]["count"] == result["count"]
    assert result["dca"]["count"] == result["count"]
    assert result["dca_win_ratio"] == pytest.approx(0.0), "오르는 장에서 분할이 이길 수 없다"


def test_compare_handles_no_rows():
    result = compare([])
    assert result["count"] == 0
    assert result["dca_win_ratio"] is None
    assert result["lump"] is None


def test_block_has_the_expected_shape():
    close = dip_then_recover(months=120)
    block, rows, result = build_dca_block(
        close, ticker="^GSPC", contrib_months=12, hold_months=36,
        asof="2026-09-07", label="S&P 500",
    )
    assert block.startswith("=== 데이터 블록 (이 안의 수치만 사용) ===")
    assert block.rstrip().endswith("=== 블록 끝 ===")
    for token in ["대상:", "전략:", "데이터 기간:", "출처:", "조회일:", "시작 시점 수:"]:
        assert token in block
    assert "[시작 시점별 최종 수익률 %]" in block
    assert "[분포 요약]" in block
    assert "[분할 매수가 앞선 횟수]" in block
    assert f"시작 시점 수: {len(rows)}" in block


def test_block_warns_below_five_start_points(capsys):
    close = rising(months=38)
    build_dca_block(close, ticker="^X", contrib_months=12, hold_months=36, asof="2026-09-07")
    assert "[경고]" in capsys.readouterr().err


def test_block_stays_quiet_with_enough_start_points(capsys):
    build_dca_block(
        rising(months=200), ticker="^X", contrib_months=12, hold_months=36,
        asof="2026-09-07",
    )
    assert capsys.readouterr().err == ""


def test_block_numbers_are_usable_by_the_validator():
    """블록이 낸 수치를 그대로 쓴 대본은 통과해야 한다."""
    close = dip_then_recover(months=120)
    block, rows, result = build_dca_block(
        close, ticker="^TEST", contrib_months=12, hold_months=36, asof="2026-09-07"
    )
    script = _minimal_script(
        f"{rows[0]['date']:%Y-%m-%d}", len(rows), f"{result['dca_win_ratio']:.2f}"
    )
    assert validate(script, block) == []


def test_to_dca_block_accepts_an_injected_stream():
    rows = dca_vs_lumpsum(rising(months=200), 12, 36)
    buffer = io.StringIO()
    to_dca_block(
        ticker="^X", rows=rows, result=compare(rows), contrib_months=12, hold_months=36,
        data_start="2000-01-03", data_end="2020-01-03", asof="2026-09-07", stream=buffer,
    )
    assert buffer.getvalue() == ""


def _minimal_script(date, starts, win_ratio):
    cues = "\n".join('[자료 화면: 근거 자료 / 화면 텍스트 "참고"]' for _ in range(5))
    return f"""## 제목 3안
1. 분할 매수는 정말 유리했나
2. 같은 돈, 다른 방식
3. 나눠 넣으면 무엇이 달라졌나

## 1. 오프닝
같은 돈을 나눠 넣으면 결과가 달라졌을까요?

{cues}

## 2. 조건 설정
두 방식을 같은 날 시작해 같은 날 끝냅니다.

## 3. 과거 사례
{date}부터 시작한 경우를 포함해 {starts}개 시점을 봤습니다.

## 4. 결과
분할 매수가 앞선 비율은 {win_ratio}입니다.

## 5. 데이터의 한계
표본이 적습니다. 기간 편향이 있습니다. 시장 구조도 달라졌습니다.

## 6. [운영자 코멘트]

## 7. 엔딩
판단은 각자.

## 숏폼 컷 3개
컷 하나 둘 셋

## 유튜브 설명란
이 영상은 과거 데이터를 정리한 정보 제공 목적이며, 투자 권유나 조언이 아닙니다.
"""


# ─── 리밸런싱 ────────────────────────────────────────────────────────

import numpy as np

from src.strategies import (
    DEFAULT_INTERVALS,
    NO_REBALANCE,
    align,
    build_rebalance_block,
    compare_intervals,
    interval_label,
    rebalance_intervals,
    simulate_rebalance,
)

HOLD = 60
SPAN = HOLD * MONTH_DAYS


def pair(values_a, values_b):
    idx = pd.bdate_range("2000-01-03", periods=len(values_a))
    return (
        pd.Series([float(v) for v in values_a], index=idx),
        pd.Series([float(v) for v in values_b], index=idx),
    )


def flat_pair(months=70):
    n = months * MONTH_DAYS
    return pair([100.0] * n, [50.0] * n)


def one_side_rising(months=70, rate=1.0004):
    n = months * MONTH_DAYS
    return pair([100 * rate**i for i in range(n)], [50.0] * n)


def one_side_swinging(months=70, amplitude=0.45):
    n = months * MONTH_DAYS
    return pair([100 * (1 + amplitude * np.sin(i / 70.0)) for i in range(n)], [50.0] * n)


def test_align_keeps_only_shared_dates():
    a = pd.Series([1.0, 2.0, 3.0], index=pd.bdate_range("2020-01-01", periods=3))
    b = pd.Series([9.0, 8.0], index=pd.bdate_range("2020-01-02", periods=2))
    aligned_a, aligned_b = align(a, b)
    assert len(aligned_a) == len(aligned_b) == 2
    assert list(aligned_a.index) == list(aligned_b.index)


def test_flat_market_returns_nothing_at_any_interval():
    a, b = flat_pair()
    for months in DEFAULT_INTERVALS:
        total, worst = simulate_rebalance(a.to_numpy(), b.to_numpy(), 0.6, months, 0, SPAN)
        assert total == pytest.approx(0.0, abs=1e-9)
        assert worst == pytest.approx(0.0, abs=1e-9)


def test_rebalancing_trims_the_winner_so_it_earns_less():
    """한쪽만 오르면 리밸런싱은 오른 쪽을 계속 덜어낸다."""
    a, b = one_side_rising()
    none_return, _ = simulate_rebalance(a.to_numpy(), b.to_numpy(), 0.6, NO_REBALANCE, 0, SPAN)
    yearly, _ = simulate_rebalance(a.to_numpy(), b.to_numpy(), 0.6, 12, 0, SPAN)
    quarterly, _ = simulate_rebalance(a.to_numpy(), b.to_numpy(), 0.6, 3, 0, SPAN)
    assert none_return > yearly > quarterly


def test_rebalancing_reduces_the_worst_drawdown():
    """이게 리밸런싱의 요점이다. 수익률만 비교하면 놓친다."""
    a, b = one_side_swinging()
    _, none_dd = simulate_rebalance(a.to_numpy(), b.to_numpy(), 0.6, NO_REBALANCE, 0, SPAN)
    _, quarterly_dd = simulate_rebalance(a.to_numpy(), b.to_numpy(), 0.6, 3, 0, SPAN)
    assert quarterly_dd > none_dd, "리밸런싱이 낙폭을 줄이지 못했다"


def test_drawdown_is_never_positive():
    a, b = one_side_swinging()
    for months in DEFAULT_INTERVALS:
        _, worst = simulate_rebalance(a.to_numpy(), b.to_numpy(), 0.6, months, 0, SPAN)
        assert worst <= 0.0


def test_interval_longer_than_holding_never_rebalances():
    a, b = one_side_rising()
    none_return, _ = simulate_rebalance(a.to_numpy(), b.to_numpy(), 0.6, NO_REBALANCE, 0, SPAN)
    same, _ = simulate_rebalance(a.to_numpy(), b.to_numpy(), 0.6, HOLD, 0, SPAN)
    assert same == pytest.approx(none_return)


def test_rows_carry_every_interval():
    a, b = one_side_rising(months=120)
    rows = rebalance_intervals(a, b, 0.6, HOLD, DEFAULT_INTERVALS)
    assert rows
    for row in rows:
        assert set(row["returns"]) == set(DEFAULT_INTERVALS)
        assert set(row["drawdowns"]) == set(DEFAULT_INTERVALS)


def test_rejects_impossible_settings():
    a, b = flat_pair()
    with pytest.raises(ValueError):
        rebalance_intervals(a, b, weight_a=0.0)
    with pytest.raises(ValueError):
        rebalance_intervals(a, b, weight_a=1.0)
    with pytest.raises(ValueError):
        rebalance_intervals(a, b, hold_months=12, intervals=(24,))
    with pytest.raises(ValueError):
        rebalance_intervals(a, b, intervals=(-3,))


def test_interval_label_names_the_no_rebalance_case():
    assert interval_label(NO_REBALANCE) == "리밸런싱 없음"
    assert interval_label(12) == "12개월"


def test_compare_intervals_reports_both_return_and_drawdown():
    a, b = one_side_swinging(months=120)
    rows = rebalance_intervals(a, b, 0.6, HOLD, DEFAULT_INTERVALS)
    result = compare_intervals(rows, DEFAULT_INTERVALS)
    for months in DEFAULT_INTERVALS:
        assert result[months]["return"]["count"] == len(rows)
        assert result[months]["drawdown"]["count"] == len(rows)


def test_rebalance_block_has_the_expected_shape():
    a, b = one_side_swinging(months=140)
    block, rows, _ = build_rebalance_block(
        a, b, ticker_a="^GSPC", ticker_b="AGG", asof="2026-09-07",
        weight_a=0.6, hold_months=HOLD, label_a="S&P 500", label_b="미국 채권",
    )
    assert block.startswith("=== 데이터 블록 (이 안의 수치만 사용) ===")
    assert block.rstrip().endswith("=== 블록 끝 ===")
    assert "[분포 요약 — 최종 수익률 %]" in block
    assert "[분포 요약 — 최대 낙폭 %]" in block
    assert "리밸런싱 없음" in block
    assert f"시작 시점 수: {len(rows)}" in block
    assert "60 대 40" in block


def test_rebalance_block_warns_below_five_start_points(capsys):
    a, b = one_side_rising(months=62)
    build_rebalance_block(a, b, ticker_a="^X", ticker_b="^Y", asof="2026-09-07",
                          hold_months=HOLD)
    assert "[경고]" in capsys.readouterr().err


def test_rebalance_block_numbers_are_usable_by_the_validator():
    a, b = one_side_swinging(months=140)
    block, rows, result = build_rebalance_block(
        a, b, ticker_a="^TEST", ticker_b="BOND", asof="2026-09-07", hold_months=HOLD
    )
    script = _minimal_script(
        f"{rows[0]['date']:%Y-%m-%d}",
        len(rows),
        f"{result[NO_REBALANCE]['return']['median']:.2f}",
    )
    assert validate(script, block) == []
