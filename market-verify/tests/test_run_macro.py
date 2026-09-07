import pandas as pd
import pytest

from src import macro, run_macro
from src.writer import AttemptUsage, ScriptGenerationError


def monthly(values, start="2000-01-01"):
    return pd.Series(
        [float(v) for v in values],
        index=pd.date_range(start=start, periods=len(values), freq="MS"),
    )


def daily_close(days=4000):
    return pd.Series(
        [100.0 + i * 0.02 for i in range(days)],
        index=pd.bdate_range(start="2000-01-03", periods=days),
    )


def inverting_curve(months=200):
    """0 위아래를 오가는 지표. 조건이 여러 번 걸린다."""
    values = []
    for i in range(months):
        values.append(1.0 if (i // 20) % 2 == 0 else -0.5)
    return monthly(values)


@pytest.fixture
def stub_sources(monkeypatch):
    monkeypatch.setattr(macro, "fetch_series", lambda *a, **k: inverting_curve())
    monkeypatch.setattr(run_macro.macro, "fetch_series", lambda *a, **k: inverting_curve())
    monkeypatch.setattr(run_macro.me, "fetch_close", lambda *a, **k: daily_close())
    monkeypatch.setenv(macro.KEY_ENV, "fred-test-key")
    monkeypatch.setenv(run_macro.KEY_ENV, "sk-ant-test-key")


def test_a_threshold_is_required():
    with pytest.raises(SystemExit):
        run_macro.parse_args(
            ["--series", "T10Y2Y", "--ticker", "^GSPC", "--start", "1990-01-01"]
        )


def test_above_and_below_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        run_macro.parse_args(
            ["--series", "T10Y2Y", "--ticker", "^GSPC", "--start", "1990-01-01",
             "--above", "1", "--below", "0"]
        )


def test_condition_text_names_the_indicator_and_the_level():
    args = run_macro.parse_args(
        ["--series", "T10Y2Y", "--ticker", "^GSPC", "--start", "1990-01-01", "--below", "0"]
    )
    _, condition, _ = run_macro.resolve_condition(inverting_curve(), args)
    assert "장단기 금리차" in condition
    assert "0 이하로 처음 내려간" in condition


def test_yoy_switches_the_condition_to_the_change_rate():
    args = run_macro.parse_args(
        ["--series", "M2SL", "--ticker", "^GSPC", "--start", "1990-01-01",
         "--below", "0", "--yoy", "12"]
    )
    series = monthly([100.0] * 12 + [95.0] * 12)
    dates, condition, used = run_macro.resolve_condition(series, args)
    assert "전년 대비 변화율" in condition
    assert "%" in condition
    assert dates, "감소로 돌아선 시점을 잡지 못했다"
    assert len(used) < len(series), "원값이 아니라 변화율에 조건을 걸어야 한다"


def test_missing_fred_key_stops_before_any_fetch(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv(macro.KEY_ENV, raising=False)
    monkeypatch.setattr(
        run_macro.macro, "fetch_series", lambda *a, **k: pytest.fail("호출되면 안 된다")
    )
    code = run_macro.main(
        ["--series", "T10Y2Y", "--ticker", "^GSPC", "--start", "1990-01-01",
         "--below", "0", "--outdir", str(tmp_path)]
    )
    assert code == 2
    assert macro.KEY_ENV in capsys.readouterr().out


def test_block_only_writes_a_block_and_skips_the_script(stub_sources, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(
        run_macro, "write_script", lambda *a, **k: pytest.fail("호출되면 안 된다")
    )
    code = run_macro.main(
        ["--series", "T10Y2Y", "--ticker", "^GSPC", "--label", "S&P 500",
         "--start", "2000-01-01", "--below", "0",
         "--outdir", str(tmp_path), "--block-only"]
    )
    assert code == 0
    block = list(tmp_path.glob("*_block.txt"))[0].read_text(encoding="utf-8")
    assert "지표: T10Y2Y" in block
    assert "FRED" in block
    assert list(tmp_path.glob("*_script.md")) == []
    assert "사례 수:" in capsys.readouterr().out


def test_filename_records_both_series_and_ticker(stub_sources, tmp_path):
    run_macro.main(
        ["--series", "T10Y2Y", "--ticker", "^GSPC", "--start", "2000-01-01",
         "--below", "0", "--outdir", str(tmp_path), "--block-only"]
    )
    assert list(tmp_path.glob("T10Y2Y_GSPC_*_block.txt"))


def test_fred_failure_is_reported_without_a_traceback(stub_sources, tmp_path, capsys, monkeypatch):
    def boom(*a, **k):
        raise macro.FredError("시리즈 ID 를 확인할 것")

    monkeypatch.setattr(run_macro.macro, "fetch_series", boom)
    code = run_macro.main(
        ["--series", "NOPE", "--ticker", "^GSPC", "--start", "2000-01-01",
         "--below", "0", "--outdir", str(tmp_path)]
    )
    assert code == 3
    assert "시리즈 ID 를 확인할 것" in capsys.readouterr().out


def test_broken_anthropic_key_stops_after_the_block(stub_sources, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv(run_macro.KEY_ENV, "\x1b[200~sk-ant-abc\x1b[201~")
    monkeypatch.setattr(
        run_macro, "write_script", lambda *a, **k: pytest.fail("호출되면 안 된다")
    )
    code = run_macro.main(
        ["--series", "T10Y2Y", "--ticker", "^GSPC", "--start", "2000-01-01",
         "--below", "0", "--outdir", str(tmp_path)]
    )
    assert code == 2
    assert len(list(tmp_path.glob("*_block.txt"))) == 1
    assert "제어문자" in capsys.readouterr().out


def test_success_saves_the_script_with_the_operator_guide(stub_sources, tmp_path, monkeypatch):
    from tests.fixtures import SCRIPT

    monkeypatch.setattr(run_macro, "write_script", lambda block, on_attempt=None: SCRIPT)
    code = run_macro.main(
        ["--series", "T10Y2Y", "--ticker", "^GSPC", "--start", "2000-01-01",
         "--below", "0", "--outdir", str(tmp_path)]
    )
    assert code == 0
    saved = list(tmp_path.glob("*_script.md"))[0].read_text(encoding="utf-8")
    assert "운영자 본인의 관점" in saved


def test_failure_saves_no_script_but_reports_the_spend(stub_sources, tmp_path, capsys, monkeypatch):
    def fail(block, on_attempt=None):
        raise ScriptGenerationError(["금지어 사용: 폭락"], 3, [AttemptUsage(1000, 500)] * 3)

    monkeypatch.setattr(run_macro, "write_script", fail)
    code = run_macro.main(
        ["--series", "T10Y2Y", "--ticker", "^GSPC", "--start", "2000-01-01",
         "--below", "0", "--outdir", str(tmp_path)]
    )
    assert code == 1
    assert list(tmp_path.glob("*_script.md")) == []
    assert "입력 3,000 / 출력 1,500" in capsys.readouterr().out
