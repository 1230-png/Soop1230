"""블록 → 그림용 숫자.

고정 문자열을 손으로 적어 두지 않고 market_events.to_block() 이 실제로 낸 블록을
읽힌다. 블록 형식이 바뀌면 여기서 깨져야 한다 — 조용히 그림만 안 나오면
한참 뒤에야 알아챈다.
"""

import pandas as pd
import pytest

from src import chart, market_events


def _rows(*triples):
    """(발생일, 1개월, 6개월, 12개월) 묶음을 블록이 받는 모양으로 바꾼다."""
    return [
        {
            "date": pd.Timestamp(date),
            "returns": dict(zip([h for h, _ in market_events.HORIZONS], values)),
        }
        for date, *values in triples
    ]


def _block(rows):
    return market_events.to_block(
        ticker="^IXIC",
        condition="주간 종가 3주 연속 하락",
        rows=rows,
        summary=market_events.summarize(rows),
        data_start="1990-01-02",
        data_end="2026-09-04",
        asof="2026-09-05",
    )


def test_reads_every_horizon_from_a_real_block():
    rows = _rows(
        ("2008-09-12", -12.34, -5.67, 3.21),
        ("2011-08-05", 4.12, 8.90, 15.00),
        ("2018-10-26", -1.00, 2.50, 7.75),
        ("2020-03-06", -9.99, 22.10, 40.20),
    )

    series = chart.parse_cases(_block(rows))

    assert [name for name, _ in series] == [
        "21거래일(1개월)", "126거래일(6개월)", "252거래일(12개월)",
    ]
    assert series[0][1] == [-12.34, 4.12, -1.00, -9.99]
    assert series[2][1] == [3.21, 15.00, 7.75, 40.20]


def test_data_shortage_cells_are_dropped_not_zeroed():
    """'데이터 부족'을 0 으로 읽으면 분포가 0 쪽으로 쏠린 거짓 그림이 된다."""
    rows = _rows(
        ("2008-09-12", -12.34, -5.67, 3.21),
        ("2011-08-05", 4.12, 8.90, 15.00),
        ("2018-10-26", -1.00, 2.50, 7.75),
        ("2026-08-03", 2.00, None, None),
    )

    series = chart.parse_cases(_block(rows))

    by_name = dict(series)
    assert by_name["21거래일(1개월)"] == [-12.34, 4.12, -1.00, 2.00]
    # 12개월은 3건만 남는다. 0 이 끼어들지 않았는지 본다.
    assert by_name["252거래일(12개월)"] == [3.21, 15.00, 7.75]


def test_horizon_with_too_few_points_is_left_out():
    """점 두 개짜리 분포는 그리지 않는다."""
    rows = _rows(
        ("2008-09-12", -12.34, -5.67, 3.21),
        ("2011-08-05", 4.12, 8.90, None),
        ("2018-10-26", -1.00, 2.50, None),
    )

    by_name = dict(chart.parse_cases(_block(rows)))

    assert "21거래일(1개월)" in by_name
    assert "252거래일(12개월)" not in by_name


def test_a_block_without_the_case_table_yields_nothing():
    """전략·토크노믹스 블록에는 사례 표가 없다. 그림 없이 넘어가야 한다."""
    assert chart.parse_cases("[분포 요약 — 최종 수익률 %]\n| 구간 | 값 |\n") == []


@pytest.mark.parametrize(
    "broken",
    [
        "",
        "[사례별 이후 수익률 %]",
        "[사례별 이후 수익률 %]\n| 발생일 | 21거래일(1개월) |\n| --- | --- |\n",
        "[사례별 이후 수익률 %]\n표가 아니라 그냥 문장이다.\n",
    ],
)
def test_broken_blocks_return_empty_instead_of_raising(broken):
    """무인 발행 자리다. 그림을 못 그리는 것이 발행을 멈출 이유가 되면 안 된다."""
    assert chart.parse_cases(broken) == []


def test_span_always_contains_zero():
    """0 이 축 밖으로 나가면 '전부 손실'인 분포가 이득처럼 보인다."""
    low, high = chart.span([("1개월", [5.0, 9.0, 12.0])])
    assert low <= 0.0 <= high

    low, high = chart.span([("1개월", [-20.0, -9.0, -3.0])])
    assert low <= 0.0 <= high


def test_span_is_shared_across_horizons():
    """구간마다 축을 따로 잡으면 눈으로 비교할 수 없다."""
    series = [("1개월", [-2.0, 1.0, 3.0]), ("12개월", [-40.0, 10.0, 55.0])]
    assert chart.span(series) == (-40.0, 55.0)
