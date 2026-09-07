import io

import pandas as pd
import pytest

from src import tokenomics as tk


# ─── 발행 스케줄 (외부 데이터 없음) ──────────────────────────────────

def test_schedule_converges_to_twenty_one_million():
    """합의 규칙이 정한 값이다. 여기서 어긋나면 계산이 틀린 것이다."""
    assert tk.terminal_supply() == pytest.approx(21_000_000, abs=1.0)


def test_reward_halves_every_epoch():
    rows = tk.halving_schedule(5)
    rewards = [row["reward"] for row in rows]
    assert rewards == [50.0, 25.0, 12.5, 6.25, 3.125]


def test_each_epoch_issues_half_of_the_previous_one():
    rows = tk.halving_schedule(5)
    for earlier, later in zip(rows, rows[1:]):
        assert later["issued"] == pytest.approx(earlier["issued"] / 2)


def test_cumulative_supply_only_grows():
    rows = tk.halving_schedule(10)
    totals = [row["supply_after"] for row in rows]
    assert totals == sorted(totals)
    assert all(t <= 21_000_000 for t in totals)


def test_inflation_falls_by_half_each_epoch_after_the_first():
    """반감기의 요점이다. 새로 풀리는 양이 절반이 되고 누적은 늘어난다."""
    rows = tk.halving_schedule(6)
    rates = [row["annual_inflation"] for row in rows if row["annual_inflation"]]
    assert rates == sorted(rates, reverse=True)
    for earlier, later in zip(rates, rates[1:]):
        assert later < earlier / 2


def test_first_epoch_has_no_inflation_rate():
    """이전 공급이 0이라 비율을 낼 수 없다. 0 으로 적으면 거짓말이다."""
    assert tk.halving_schedule(3)[0]["annual_inflation"] is None


def test_recorded_halvings_are_not_marked_estimated():
    rows = tk.halving_schedule(8)
    for row in rows:
        if row["epoch"] in tk.RECORDED_HALVINGS:
            assert row["estimated"] is False
            assert row["date"] == tk.RECORDED_HALVINGS[row["epoch"]]
        else:
            assert row["estimated"] is True


def test_epoch_length_is_about_four_years():
    assert 3.9 < tk.epoch_years() < 4.1


def test_schedule_rejects_a_bad_epoch_count():
    with pytest.raises(ValueError):
        tk.halving_schedule(0)


def test_schedule_block_states_it_used_no_external_data():
    block, rows = tk.build_schedule_block("비트코인", "2026-09-07", epochs=6)
    assert "외부 데이터 없음" in block
    assert "21,000,000.00" in block
    assert "[반감기 구간별 발행]" in block
    assert block.rstrip().endswith("=== 블록 끝 ===")
    assert f"구간 수: {len(rows)}" in block


def test_schedule_block_labels_undated_epochs():
    block, _ = tk.build_schedule_block("비트코인", "2026-09-07", epochs=8)
    assert "미도래" in block


def test_schedule_block_notes_estimated_dates(capsys):
    tk.build_schedule_block("비트코인", "2026-09-07", epochs=8)
    assert "[참고]" in capsys.readouterr().err


# ─── 실측 희석률 ─────────────────────────────────────────────────────

def chart(days, price_fn, supply_fn):
    start = pd.Timestamp("2015-01-01")
    prices, caps = [], []
    for i in range(days):
        ms = int((start + pd.Timedelta(days=i)).timestamp() * 1000)
        price = price_fn(i)
        prices.append([ms, price])
        caps.append([ms, price * supply_fn(i)])
    return {"prices": prices, "market_caps": caps}


def fake_fetcher(payload):
    return lambda coin_id, params: payload


def test_fetch_returns_aligned_price_and_cap():
    payload = chart(10, lambda i: 100.0 + i, lambda i: 1000.0)
    price, cap = tk.fetch_market_chart("bitcoin", fetcher=fake_fetcher(payload))
    assert len(price) == len(cap) == 10
    assert list(price.index) == list(cap.index)


def test_fetch_without_data_is_an_error():
    with pytest.raises(tk.TokenomicsError):
        tk.fetch_market_chart("nope", fetcher=fake_fetcher({"prices": [], "market_caps": []}))


def test_supply_is_cap_over_price():
    payload = chart(5, lambda i: 50.0, lambda i: 2000.0)
    price, cap = tk.fetch_market_chart("x", fetcher=fake_fetcher(payload))
    assert list(tk.implied_supply(price, cap)) == pytest.approx([2000.0] * 5)


def test_supply_derivation_rejects_zero_price():
    index = pd.date_range("2020-01-01", periods=3)
    with pytest.raises(tk.TokenomicsError):
        tk.implied_supply(pd.Series([1.0, 0.0, 2.0], index=index),
                          pd.Series([1.0, 1.0, 1.0], index=index))


def test_growth_is_percent_over_the_window():
    index = pd.date_range("2020-01-01", periods=400)
    supply = pd.Series([100.0] * 365 + [110.0] * 35, index=index)
    assert tk.supply_growth(supply, 365).iloc[-1] == pytest.approx(10.0)


def test_growth_rejects_a_bad_window():
    with pytest.raises(ValueError):
        tk.supply_growth(pd.Series([1.0, 2.0]), 0)


def test_dilution_block_shows_supply_growth_and_price():
    payload = chart(1200, lambda i: 100.0 + i * 0.5, lambda i: 1000.0 + i)
    price, cap = tk.fetch_market_chart("bitcoin", fetcher=fake_fetcher(payload))
    block, samples = tk.build_dilution_block(
        "bitcoin", "비트코인", price, cap, "2026-09-07"
    )
    assert "유통량 산출: 시가총액 ÷ 가격" in block
    assert "CoinGecko" in block
    assert "[연도별 유통량과 전년 대비 증가율]" in block
    assert f"관측 구간 수: {len(samples)}" in block
    assert samples[0]["growth"] > 0


def test_dilution_needs_more_history_than_the_window():
    payload = chart(100, lambda i: 100.0, lambda i: 1000.0)
    price, cap = tk.fetch_market_chart("x", fetcher=fake_fetcher(payload))
    with pytest.raises(tk.TokenomicsError):
        tk.build_dilution_block("x", "X", price, cap, "2026-09-07", periods=365)


def test_dilution_block_warns_on_too_few_windows(capsys):
    payload = chart(400, lambda i: 100.0, lambda i: 1000.0 + i)
    price, cap = tk.fetch_market_chart("x", fetcher=fake_fetcher(payload))
    tk.build_dilution_block("x", "X", price, cap, "2026-09-07")
    assert "[경고]" in capsys.readouterr().err


def test_yearly_samples_thin_the_table_out():
    """매일 찍으면 표가 수천 줄이 된다."""
    payload = chart(1500, lambda i: 100.0, lambda i: 1000.0 + i)
    price, cap = tk.fetch_market_chart("x", fetcher=fake_fetcher(payload))
    _, samples = tk.build_dilution_block("x", "X", price, cap, "2026-09-07")
    assert len(samples) <= 5


def test_block_accepts_an_injected_stream():
    buffer = io.StringIO()
    tk.to_schedule_block("비트코인", tk.halving_schedule(8), "2026-09-07",
                         tk.terminal_supply(), stream=buffer)
    assert "[참고]" in buffer.getvalue()


# ─── 코인게코 키와 오류 안내 ─────────────────────────────────────────

def test_coingecko_key_check_catches_the_usual_mistakes():
    assert "설정되지 않았다" in tk.check_coingecko_key({})
    assert "제어문자" in tk.check_coingecko_key({tk.COINGECKO_KEY_ENV: "\x1b[200~k\x1b[201~"})
    assert tk.check_coingecko_key({tk.COINGECKO_KEY_ENV: "cg-demo-abc"}) is None


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, tk.COINGECKO_KEY_ENV),
        (429, "요청 한도"),
        (404, "코인 ID"),
        (500, "HTTP 500"),
    ],
)
def test_http_status_becomes_a_readable_cause(status, expected):
    """401 만 덩그러니 던지면 무엇을 고쳐야 할지 알 수 없다."""
    assert expected in tk._http_hint(status, "bitcoin")


def test_schedule_mode_never_needs_the_coingecko_key():
    """발행 스케줄은 합의 규칙에서 계산한다. 키를 요구하면 안 된다."""
    block, _ = tk.build_schedule_block("비트코인", "2026-09-07", epochs=6)
    assert "CoinGecko" not in block
    assert "외부 데이터 없음" in block
