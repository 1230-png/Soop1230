import io

import pandas as pd
import pytest

from src import macro
from src.validator import validate


def monthly(values, start="2000-01-01"):
    return pd.Series(
        [float(v) for v in values],
        index=pd.date_range(start=start, periods=len(values), freq="MS"),
    )


def daily_close(days=3000, start="2000-01-03"):
    return pd.Series(
        [100.0 + i * 0.02 for i in range(days)],
        index=pd.bdate_range(start=start, periods=days),
    )


def fake_fetcher(observations):
    return lambda params: {"observations": observations}


# ─── FRED 조회 ───────────────────────────────────────────────────────

def test_fetch_parses_observations():
    fetch = fake_fetcher(
        [{"date": "2020-01-01", "value": "1.5"}, {"date": "2020-02-01", "value": "2.0"}]
    )
    series = macro.fetch_series("T10Y2Y", "2020-01-01", api_key="k", fetcher=fetch)
    assert list(series) == [1.5, 2.0]
    assert series.index[0] == pd.Timestamp("2020-01-01")


def test_fetch_drops_missing_marks():
    """FRED 는 결측을 '.' 으로 준다. 0 으로 읽으면 조건이 엉뚱하게 걸린다."""
    fetch = fake_fetcher(
        [
            {"date": "2020-01-01", "value": "."},
            {"date": "2020-02-01", "value": ""},
            {"date": "2020-03-01", "value": "3.0"},
        ]
    )
    series = macro.fetch_series("X", "2020-01-01", api_key="k", fetcher=fetch)
    assert list(series) == [3.0]


def test_fetch_sorts_by_date():
    fetch = fake_fetcher(
        [{"date": "2020-03-01", "value": "3"}, {"date": "2020-01-01", "value": "1"}]
    )
    series = macro.fetch_series("X", "2020-01-01", api_key="k", fetcher=fetch)
    assert list(series) == [1.0, 3.0]


def test_fetch_without_any_value_is_an_error():
    with pytest.raises(macro.FredError):
        macro.fetch_series("X", "2020-01-01", api_key="k", fetcher=fake_fetcher([]))


def test_fetch_without_a_key_is_an_error():
    with pytest.raises(macro.FredError):
        macro.fetch_series("X", "2020-01-01", api_key="", fetcher=fake_fetcher([]))


def test_key_check_catches_the_usual_mistakes():
    assert "설정되지 않았다" in macro.check_api_key({})
    assert "제어문자" in macro.check_api_key({macro.KEY_ENV: "\x1b[200~abc\x1b[201~"})
    assert macro.check_api_key({macro.KEY_ENV: "abcdef"}) is None


def test_known_series_get_korean_names():
    assert macro.series_name("T10Y2Y") == "장단기 금리차 (10년 - 2년)"
    assert macro.series_name("MADEUP") == "MADEUP"


# ─── 조건 ────────────────────────────────────────────────────────────

def test_cross_below_marks_only_the_entry():
    series = monthly([1.0, 0.5, -0.2, -0.5, 0.3, -0.1])
    hits = macro.cross_below(series, 0.0)
    assert len(hits) == 2
    assert series[hits[0]] == -0.2
    assert series[hits[1]] == -0.1


def test_cross_above_marks_only_the_entry():
    series = monthly([1.0, 4.0, 5.0, 2.0, 6.0])
    hits = macro.cross_above(series, 4.0)
    assert len(hits) == 2
    assert series[hits[0]] == 4.0
    assert series[hits[1]] == 6.0


def test_no_crossing_yields_nothing():
    assert macro.cross_below(monthly([1.0, 2.0, 3.0]), 0.0) == []


def test_yoy_change_is_percent_over_the_period():
    series = monthly([100.0] * 12 + [110.0])
    change = macro.yoy_change(series, 12)
    assert change.iloc[-1] == pytest.approx(10.0)


def test_yoy_rejects_a_bad_period():
    with pytest.raises(ValueError):
        macro.yoy_change(monthly([1.0, 2.0]), 0)


# ─── 거래일 매핑 ─────────────────────────────────────────────────────

def test_indicator_dates_move_to_the_next_trading_day():
    """지표 발표일이 휴장일이면 그 날 가격이 없다."""
    close = daily_close()
    saturday = pd.Timestamp("2001-01-06")
    mapped = macro.to_trading_days([saturday], close)
    assert len(mapped) == 1
    assert mapped[0] in close.index
    assert mapped[0] >= saturday


def test_dates_landing_on_the_same_trading_day_are_collapsed():
    close = daily_close()
    same = [pd.Timestamp("2001-01-06"), pd.Timestamp("2001-01-07")]
    assert len(macro.to_trading_days(same, close)) == 1


def test_dates_after_the_price_history_are_dropped():
    close = daily_close(days=100)
    assert macro.to_trading_days([pd.Timestamp("2099-01-01")], close) == []


def test_mapping_keeps_chronological_order():
    close = daily_close()
    dates = [pd.Timestamp("2005-06-01"), pd.Timestamp("2002-03-01")]
    mapped = macro.to_trading_days(dates, close)
    assert mapped == sorted(mapped)


# ─── 블록 ────────────────────────────────────────────────────────────

def _events(close, count=8, step=300):
    return [close.index[200 + i * step] for i in range(count)]


def test_block_names_both_sources():
    close = daily_close()
    block, rows, _ = macro.build_block(
        macro=monthly([1.0] * 240),
        close=close,
        series_id="T10Y2Y",
        ticker="^GSPC",
        condition="장단기 금리차가 0 이하로 처음 내려간 시점",
        event_dates=_events(close),
        asof="2026-09-07",
        label="S&P 500",
    )
    assert "지표: T10Y2Y (장단기 금리차 (10년 - 2년))" in block
    assert "지표 기간:" in block
    assert "FRED" in block and "Yahoo Finance" in block
    assert "대상: ^GSPC (S&P 500)" in block
    assert block.rstrip().endswith("=== 블록 끝 ===")
    assert f"사례 수: {len(rows)}" in block


def test_block_applies_the_minimum_gap_filter():
    """지표가 월간이면 조건이 연달아 걸린다. 걸러야 표본이 부풀지 않는다."""
    close = daily_close()
    clustered = list(close.index[200:220])
    _, rows, _ = macro.build_block(
        macro=monthly([1.0] * 240), close=close, series_id="X", ticker="^Y",
        condition="테스트", event_dates=clustered, asof="2026-09-07",
    )
    assert len(rows) == 1


def test_block_warns_below_five_cases(capsys):
    close = daily_close()
    macro.build_block(
        macro=monthly([1.0] * 240), close=close, series_id="X", ticker="^Y",
        condition="테스트", event_dates=_events(close, count=2), asof="2026-09-07",
    )
    assert "[경고]" in capsys.readouterr().err


def test_block_accepts_an_injected_stream():
    close = daily_close()
    buffer = io.StringIO()
    macro.to_block(
        series_id="X", ticker="^Y", condition="테스트", rows=[], summary={},
        macro_start="2000-01-01", macro_end="2020-01-01",
        price_start="2000-01-03", price_end="2020-01-03",
        asof="2026-09-07", stream=buffer,
    )
    assert "[경고]" in buffer.getvalue()


def test_block_numbers_are_usable_by_the_validator():
    close = daily_close()
    block, rows, _ = macro.build_block(
        macro=monthly([1.0] * 240), close=close, series_id="T10Y2Y", ticker="^TEST",
        condition="테스트 조건", event_dates=_events(close), asof="2026-09-07",
    )
    script = _minimal_script(f"{rows[0]['date']:%Y-%m-%d}", len(rows))
    assert validate(script, block) == []


def _minimal_script(date, count):
    cues = "\n".join('[자료 화면: 근거 자료 / 화면 텍스트 "참고"]' for _ in range(5))
    return f"""## 제목 3안
1. 지표가 이 상태였을 때
2. 과거 기록은
3. 그 뒤 어떻게 됐나

## 1. 오프닝
지표가 이 상태였을 때 지수는 어떻게 움직였을까요?

{cues}

## 2. 조건 설정
지표 조건을 정의합니다.

## 3. 과거 사례
{date}에 조건이 성립했습니다.

## 4. 결과
사례는 {count}건입니다.

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
