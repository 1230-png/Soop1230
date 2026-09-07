import pandas as pd
import pytest

from src import run_strategy
from src.strategies import MONTH_DAYS
from src.writer import AttemptUsage, ScriptGenerationError


def dip_then_recover(months=160, contrib=12, step=0.15):
    down = [100 - i * step for i in range(contrib * MONTH_DAYS)]
    up = [down[-1] + i * step for i in range(months * MONTH_DAYS - len(down))]
    values = down + up
    return pd.Series(
        [float(v) for v in values], index=pd.bdate_range("2000-01-03", periods=len(values))
    )


@pytest.fixture
def stub_market(monkeypatch):
    close = dip_then_recover()
    monkeypatch.setattr(run_strategy.me, "fetch_close", lambda *a, **k: close)
    monkeypatch.setenv(run_strategy.KEY_ENV, "sk-ant-test-key")
    return close


def test_hold_must_cover_the_contribution_period():
    with pytest.raises(SystemExit):
        run_strategy.parse_args(
            ["--ticker", "^X", "--start", "1990-01-01",
             "--contrib-months", "24", "--hold-months", "12"]
        )


def test_block_only_writes_a_block_and_skips_the_api(stub_market, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(
        run_strategy, "write_script", lambda *a, **k: pytest.fail("호출되면 안 된다")
    )
    code = run_strategy.main(
        ["--ticker", "^GSPC", "--start", "1990-01-01",
         "--outdir", str(tmp_path), "--block-only"]
    )
    out = capsys.readouterr().out
    assert code == 0
    blocks = list(tmp_path.glob("*_block.txt"))
    assert len(blocks) == 1
    assert "[분할 매수가 앞선 횟수]" in blocks[0].read_text(encoding="utf-8")
    assert "시작 시점" in out
    assert "분할 매수가 앞선 비율" in out
    assert list(tmp_path.glob("*_script.md")) == []


def test_filename_records_the_settings(stub_market, tmp_path):
    run_strategy.main(
        ["--ticker", "^GSPC", "--start", "1990-01-01", "--contrib-months", "6",
         "--hold-months", "24", "--outdir", str(tmp_path), "--block-only"]
    )
    assert list(tmp_path.glob("GSPC_dca6-hold24_*_block.txt"))


def test_broken_key_stops_before_any_api_call(stub_market, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv(run_strategy.KEY_ENV, "\x1b[200~sk-ant-abc\x1b[201~")
    monkeypatch.setattr(
        run_strategy, "write_script", lambda *a, **k: pytest.fail("호출되면 안 된다")
    )
    code = run_strategy.main(
        ["--ticker", "^GSPC", "--start", "1990-01-01", "--outdir", str(tmp_path)]
    )
    assert code == 2
    assert len(list(tmp_path.glob("*_block.txt"))) == 1
    assert "제어문자" in capsys.readouterr().out


def test_success_saves_the_script_with_the_operator_guide(stub_market, tmp_path, monkeypatch):
    from tests.fixtures import SCRIPT

    monkeypatch.setattr(run_strategy, "write_script", lambda block, on_attempt=None: SCRIPT)
    code = run_strategy.main(
        ["--ticker", "^GSPC", "--start", "1990-01-01", "--outdir", str(tmp_path)]
    )
    assert code == 0
    saved = list(tmp_path.glob("*_script.md"))[0].read_text(encoding="utf-8")
    assert "## 6. [운영자 코멘트]" in saved
    assert "운영자 본인의 관점" in saved


def test_failure_saves_no_script_but_reports_the_spend(stub_market, tmp_path, capsys, monkeypatch):
    def fail(block, on_attempt=None):
        raise ScriptGenerationError(["금지어 사용: 폭락"], 3, [AttemptUsage(1000, 500)] * 3)

    monkeypatch.setattr(run_strategy, "write_script", fail)
    code = run_strategy.main(
        ["--ticker", "^GSPC", "--start", "1990-01-01", "--outdir", str(tmp_path)]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert list(tmp_path.glob("*_script.md")) == []
    assert "입력 3,000 / 출력 1,500" in out


# ─── 리밸런싱 모드 ───────────────────────────────────────────────────

import numpy as np

from src.strategies import MONTH_DAYS as MD


def swinging_pair(months=140):
    n = months * MD
    idx = pd.bdate_range("1990-01-02", periods=n)
    a = pd.Series([100 * (1.0003**i) * (1 + 0.30 * np.sin(i / 85.0)) for i in range(n)], index=idx)
    b = pd.Series([50 * (1.00008**i) for i in range(n)], index=idx)
    return a, b


@pytest.fixture
def stub_pair(monkeypatch):
    a, b = swinging_pair()
    calls = []

    def fake_fetch(ticker, *args, **kwargs):
        calls.append(ticker)
        return a if ticker == "^GSPC" else b

    monkeypatch.setattr(run_strategy.me, "fetch_close", fake_fetch)
    monkeypatch.setenv(run_strategy.KEY_ENV, "sk-ant-test-key")
    return calls


def test_rebalance_needs_a_second_ticker():
    with pytest.raises(SystemExit):
        run_strategy.parse_args(
            ["--strategy", "rebalance", "--ticker", "^GSPC", "--start", "1990-01-01"]
        )


def test_weight_must_be_between_zero_and_one():
    for bad in ["0", "1", "1.5"]:
        with pytest.raises(SystemExit):
            run_strategy.parse_args(
                ["--strategy", "rebalance", "--ticker", "^A", "--ticker-b", "B",
                 "--start", "1990-01-01", "--weight", bad]
            )


def test_intervals_must_parse_and_fit_the_holding_period():
    for bad in ["0,three", "", "0,-3"]:
        with pytest.raises(SystemExit):
            run_strategy.parse_args(
                ["--strategy", "rebalance", "--ticker", "^A", "--ticker-b", "B",
                 "--start", "1990-01-01", "--intervals", bad]
            )
    with pytest.raises(SystemExit):
        run_strategy.parse_args(
            ["--strategy", "rebalance", "--ticker", "^A", "--ticker-b", "B",
             "--start", "1990-01-01", "--hold-months", "12", "--intervals", "0,24"]
        )


def test_rebalance_fetches_both_assets(stub_pair, tmp_path):
    run_strategy.main(
        ["--strategy", "rebalance", "--ticker", "^GSPC", "--ticker-b", "AGG",
         "--start", "1990-01-01", "--hold-months", "60",
         "--outdir", str(tmp_path), "--block-only"]
    )
    assert stub_pair == ["^GSPC", "AGG"]


def test_rebalance_block_reports_returns_and_drawdowns(stub_pair, tmp_path, capsys):
    code = run_strategy.main(
        ["--strategy", "rebalance", "--ticker", "^GSPC", "--ticker-b", "AGG",
         "--start", "1990-01-01", "--hold-months", "60", "--label", "S&P 500",
         "--outdir", str(tmp_path), "--block-only"]
    )
    assert code == 0
    block = list(tmp_path.glob("*_block.txt"))[0].read_text(encoding="utf-8")
    assert "[분포 요약 — 최대 낙폭 %]" in block
    assert "리밸런싱 없음" in block
    out = capsys.readouterr().out
    assert "낙폭 중앙값" in out


def test_rebalance_filename_records_the_weight(stub_pair, tmp_path):
    run_strategy.main(
        ["--strategy", "rebalance", "--ticker", "^GSPC", "--ticker-b", "AGG",
         "--start", "1990-01-01", "--hold-months", "60", "--weight", "0.7",
         "--outdir", str(tmp_path), "--block-only"]
    )
    assert list(tmp_path.glob("GSPC_reb70-hold60_*_block.txt"))


def test_custom_intervals_reach_the_block(stub_pair, tmp_path):
    run_strategy.main(
        ["--strategy", "rebalance", "--ticker", "^GSPC", "--ticker-b", "AGG",
         "--start", "1990-01-01", "--hold-months", "60", "--intervals", "0,6",
         "--outdir", str(tmp_path), "--block-only"]
    )
    block = list(tmp_path.glob("*_block.txt"))[0].read_text(encoding="utf-8")
    assert "6개월" in block
    assert "3개월" not in block
