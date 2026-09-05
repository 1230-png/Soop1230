import pandas as pd
import pytest

from src import run
from src.writer import ScriptGenerationError
from tests.fixtures import SCRIPT


def falling_close():
    values = list(range(500, 100, -1))
    return pd.Series(
        [float(v) for v in values], index=pd.bdate_range("2000-01-03", periods=len(values))
    )


@pytest.fixture
def stub_market(monkeypatch):
    close = falling_close()
    monkeypatch.setattr(run.me, "fetch_close", lambda *a, **k: close)
    return close


def test_parse_args_reads_the_documented_invocation():
    args = run.parse_args(
        ["--ticker", "^GSPC", "--condition", "down-weeks", "--n", "3", "--start", "1990-01-01"]
    )
    assert args.ticker == "^GSPC"
    assert args.condition == "down-weeks"
    assert args.n == 3
    assert args.start == "1990-01-01"


def test_threshold_requires_level():
    with pytest.raises(SystemExit):
        run.parse_args(["--ticker", "^VIX", "--condition", "threshold", "--start", "1990-01-01"])


def test_unknown_condition_is_rejected():
    with pytest.raises(SystemExit):
        run.parse_args(["--ticker", "^GSPC", "--condition", "moon", "--start", "1990-01-01"])


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["--condition", "down-weeks", "--n", "4"], "주간 종가 4주 연속 하락"),
        (["--condition", "drawdown", "--pct", "20"], "전고점 대비 20% 하락 구간 첫 진입"),
        (["--condition", "threshold", "--level", "30"], "30 이상 첫 돌파"),
    ],
)
def test_resolve_events_describes_each_condition(argv, expected):
    args = run.parse_args(["--ticker", "^X", "--start", "1990-01-01"] + argv)
    _, condition = run.resolve_events(falling_close(), args)
    assert condition == expected


def test_slug_strips_ticker_punctuation():
    assert run._slug("^GSPC") == "GSPC"
    assert run._slug("BTC-USD") == "BTC-USD"


def test_block_only_writes_block_and_skips_the_api(stub_market, tmp_path, capsys, monkeypatch):
    def explode(*a, **k):
        raise AssertionError("--block-only 인데 API를 호출했다")

    monkeypatch.setattr(run, "write_script", explode)
    code = run.main(
        [
            "--ticker", "^GSPC", "--condition", "down-weeks", "--n", "3",
            "--start", "2000-01-01", "--outdir", str(tmp_path), "--block-only",
        ]
    )
    assert code == 0
    blocks = list(tmp_path.glob("*_block.txt"))
    assert len(blocks) == 1
    assert "=== 데이터 블록" in blocks[0].read_text(encoding="utf-8")
    assert list(tmp_path.glob("*_script.md")) == []
    assert "사례 수:" in capsys.readouterr().out


def test_success_saves_block_and_script(stub_market, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(run, "write_script", lambda block, on_attempt=None: SCRIPT)
    code = run.main(
        [
            "--ticker", "^GSPC", "--condition", "down-weeks", "--n", "3",
            "--start", "2000-01-01", "--outdir", str(tmp_path),
        ]
    )
    assert code == 0
    assert len(list(tmp_path.glob("*_block.txt"))) == 1
    assert list(tmp_path.glob("*_script.md"))[0].read_text(encoding="utf-8") == SCRIPT
    assert "최종 위반 0건" in capsys.readouterr().out


def test_failure_reports_count_and_saves_no_script(stub_market, tmp_path, capsys, monkeypatch):
    def fail(block, on_attempt=None):
        raise ScriptGenerationError(["금지어 사용: 폭락", "데이터 블록에 없는 숫자: 99"], 3)

    monkeypatch.setattr(run, "write_script", fail)
    code = run.main(
        [
            "--ticker", "^GSPC", "--condition", "down-weeks", "--n", "3",
            "--start", "2000-01-01", "--outdir", str(tmp_path),
        ]
    )
    assert code == 1
    assert list(tmp_path.glob("*_script.md")) == [], "실패했는데 대본을 저장했다"
    assert len(list(tmp_path.glob("*_block.txt"))) == 1
    assert "최종 위반 2건" in capsys.readouterr().out
