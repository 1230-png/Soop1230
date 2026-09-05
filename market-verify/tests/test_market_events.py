import io

import pandas as pd
import pytest

from src.market_events import (
    HORIZONS,
    MIN_GAP_TRADING_DAYS,
    _extract_close,
    apply_min_gap,
    build_block,
    down_weeks,
    drawdown_entry,
    forward_returns,
    summarize,
    threshold_break,
    to_block,
)
from src.validator import validate


def business_series(values, start="2000-01-03"):
    index = pd.bdate_range(start=start, periods=len(values))
    return pd.Series([float(v) for v in values], index=index)


def test_extract_close_handles_plain_columns():
    index = pd.bdate_range("2020-01-01", periods=3)
    df = pd.DataFrame({"Close": [1.0, 2.0, 3.0], "Volume": [1, 1, 1]}, index=index)
    assert list(_extract_close(df)) == [1.0, 2.0, 3.0]


def test_extract_close_handles_multiindex_columns():
    index = pd.bdate_range("2020-01-01", periods=3)
    columns = pd.MultiIndex.from_tuples([("Close", "^GSPC"), ("Volume", "^GSPC")])
    df = pd.DataFrame([[1.0, 10], [2.0, 10], [3.0, 10]], index=index, columns=columns)
    assert list(_extract_close(df)) == [1.0, 2.0, 3.0]


def test_extract_close_handles_reversed_multiindex_levels():
    index = pd.bdate_range("2020-01-01", periods=3)
    columns = pd.MultiIndex.from_tuples([("^GSPC", "Close"), ("^GSPC", "Volume")])
    df = pd.DataFrame([[1.0, 10], [2.0, 10], [3.0, 10]], index=index, columns=columns)
    assert list(_extract_close(df)) == [1.0, 2.0, 3.0]


def test_extract_close_drops_missing_values():
    index = pd.bdate_range("2020-01-01", periods=3)
    df = pd.DataFrame({"Close": [1.0, None, 3.0]}, index=index)
    assert list(_extract_close(df)) == [1.0, 3.0]


def test_down_weeks_finds_three_week_streak():
    # 주 5거래일씩, 주간 종가가 계속 내려가도록 단조 감소 구간을 만든다.
    close = business_series(list(range(100, 60, -1)))
    hits = down_weeks(close, n=3)
    assert hits, "연속 하락 구간을 잡지 못했다"
    assert all(isinstance(d, pd.Timestamp) for d in hits)


def test_down_weeks_ignores_rising_market():
    close = business_series(list(range(100, 140)))
    assert down_weeks(close, n=3) == []


def test_down_weeks_respects_n():
    values = [100, 101, 102, 103, 104] * 2 + [90] * 5 + [80] * 5 + [70] * 5
    close = business_series(values)
    assert len(down_weeks(close, n=2)) >= len(down_weeks(close, n=3))


def test_down_weeks_rejects_bad_n():
    with pytest.raises(ValueError):
        down_weeks(business_series([1, 2, 3]), n=0)


def test_drawdown_entry_triggers_once_per_episode():
    values = [100] * 5 + [80] * 5 + [85] * 5 + [120] * 5 + [95] * 5
    close = business_series(values)
    hits = drawdown_entry(close, pct=10.0)
    assert len(hits) == 2
    assert close[hits[0]] == 80.0
    assert close[hits[1]] == 95.0


def test_drawdown_entry_ignores_shallow_dip():
    close = business_series([100] * 5 + [95] * 5)
    assert drawdown_entry(close, pct=10.0) == []


def test_drawdown_entry_rejects_bad_pct():
    with pytest.raises(ValueError):
        drawdown_entry(business_series([1, 2]), pct=0)


def test_threshold_break_marks_first_crossing_only():
    series = business_series([10, 12, 31, 35, 33, 20, 15, 40])
    hits = threshold_break(series, 30)
    assert len(hits) == 2
    assert series[hits[0]] == 31.0
    assert series[hits[1]] == 40.0


def test_apply_min_gap_collapses_clustered_events():
    close = business_series(list(range(300)))
    clustered = list(close.index[:20])
    assert apply_min_gap(clustered, close) == [close.index[0]]


def test_apply_min_gap_keeps_events_beyond_the_gap():
    close = business_series(list(range(300)))
    dates = [close.index[0], close.index[MIN_GAP_TRADING_DAYS], close.index[200]]
    assert apply_min_gap(dates, close) == dates


def test_apply_min_gap_boundary_is_inclusive():
    close = business_series(list(range(300)))
    just_short = [close.index[0], close.index[MIN_GAP_TRADING_DAYS - 1]]
    assert apply_min_gap(just_short, close) == [close.index[0]]


def test_apply_min_gap_sorts_input():
    close = business_series(list(range(300)))
    unsorted = [close.index[200], close.index[0]]
    assert apply_min_gap(unsorted, close) == [close.index[0], close.index[200]]


def test_forward_returns_computes_expected_percentages():
    close = business_series([100.0] * 300)
    close.iloc[21] = 110.0
    rows = forward_returns(close, [close.index[0]])
    assert rows[0]["returns"][21] == pytest.approx(10.0)
    assert rows[0]["returns"][126] == pytest.approx(0.0)


def test_forward_returns_returns_none_when_data_is_short():
    close = business_series([100.0] * 30)
    rows = forward_returns(close, [close.index[0]])
    assert rows[0]["returns"][21] is not None
    assert rows[0]["returns"][126] is None
    assert rows[0]["returns"][252] is None


def test_summarize_reports_distribution_not_just_mean():
    rows = [
        {"date": None, "returns": {21: -30.0, 126: None, 252: None}},
        {"date": None, "returns": {21: 50.0, 126: None, 252: None}},
    ]
    stat = summarize(rows)[21]
    assert stat["count"] == 2
    assert stat["mean"] == pytest.approx(10.0)
    assert stat["min"] == pytest.approx(-30.0)
    assert stat["max"] == pytest.approx(50.0)
    assert stat["positive_ratio"] == pytest.approx(50.0)
    assert summarize(rows)[126] is None


def test_to_block_has_required_shape():
    rows = [{"date": pd.Timestamp("2010-05-07"), "returns": {21: 1.0, 126: 2.0, 252: None}}]
    block = to_block(
        ticker="^GSPC",
        condition="테스트 조건",
        rows=rows,
        summary=summarize(rows),
        data_start="2000-01-03",
        data_end="2020-01-03",
        asof="2025-01-02",
        label="S&P 500",
        stream=io.StringIO(),
    )
    assert block.startswith("=== 데이터 블록 (이 안의 수치만 사용) ===")
    assert block.rstrip().endswith("=== 블록 끝 ===")
    for token in ["대상:", "조건:", "데이터 기간:", "출처:", "조회일:", "주가 기준:", "사례 수:"]:
        assert token in block
    assert "[사례별 이후 수익률 %]" in block
    assert "[분포 요약]" in block
    assert "2010-05-07" in block
    assert "데이터 부족" in block


def test_to_block_warns_below_five_samples(capsys):
    rows = [{"date": pd.Timestamp("2010-05-07"), "returns": {21: 1.0, 126: 2.0, 252: 3.0}}]
    to_block(
        ticker="^GSPC",
        condition="테스트 조건",
        rows=rows,
        summary=summarize(rows),
        data_start="2000-01-03",
        data_end="2020-01-03",
        asof="2025-01-02",
    )
    assert "[경고]" in capsys.readouterr().err


def test_to_block_stays_quiet_with_enough_samples(capsys):
    rows = [
        {"date": pd.Timestamp(f"20{10 + i}-05-07"), "returns": {21: 1.0, 126: 2.0, 252: 3.0}}
        for i in range(6)
    ]
    to_block(
        ticker="^GSPC",
        condition="테스트 조건",
        rows=rows,
        summary=summarize(rows),
        data_start="2000-01-03",
        data_end="2020-01-03",
        asof="2025-01-02",
    )
    assert capsys.readouterr().err == ""


def test_build_block_applies_gap_filter_end_to_end():
    close = business_series(list(range(400, 0, -1)))
    raw = down_weeks(close, n=3)
    block, rows, summary = build_block(
        close, raw, ticker="^TEST", condition="주간 종가 3주 연속 하락", asof="2025-01-02"
    )
    assert len(rows) < len(raw)
    assert f"사례 수: {len(rows)}" in block
    assert summary[21] is not None


def test_block_numbers_are_self_consistent_for_the_validator():
    """블록이 만든 수치는 그대로 대본에 쓸 수 있어야 한다."""
    close = business_series(list(range(400, 0, -1)))
    block, rows, _ = build_block(
        close, down_weeks(close, n=3), ticker="^TEST", condition="테스트", asof="2025-01-02"
    )
    quoted = f"{rows[0]['date']:%Y-%m-%d}"
    script = _minimal_script(quoted, len(rows))
    assert validate(script, block) == []


def _minimal_script(date, sample_count):
    cues = "\n".join(f"[자료 화면: 자료 {i} / 화면 텍스트 \"참고\"]" for i in range(1, 6))
    return f"""## 제목 3안
1. 테스트 제목
2. 테스트 제목
3. 테스트 제목

## 1. 오프닝
조건이 성립한 뒤 지수는 어떻게 움직였을까요?

{cues}

## 2. 조건 설정
조건을 정의합니다.

## 3. 과거 사례
{date}에 조건이 성립했습니다.

## 4. 결과
사례 수는 {sample_count}건입니다.

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
