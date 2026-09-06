import pandas as pd
import pytest

from src import run
from src.writer import APICallError, AttemptUsage, ScriptGenerationError
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
    # main() 은 API 호출 전에 키 형태를 본다. 테스트에는 형태만 맞는 값을 준다.
    monkeypatch.setenv(run.KEY_ENV, "sk-ant-test-key")
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
    saved = list(tmp_path.glob("*_script.md"))[0].read_text(encoding="utf-8")
    # 저장본은 운영자 칸 작성 안내만 더 들어간다. 나머지는 모델 출력 그대로다.
    assert saved == run.add_operator_guide(SCRIPT)
    assert saved.replace(run.OPERATOR_GUIDE + "\n", "") == SCRIPT
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


def test_success_prints_per_attempt_and_total_usage(stub_market, tmp_path, capsys, monkeypatch):
    def fake_write(block, on_attempt=None):
        on_attempt(1, ["금지어 사용: 급등"], AttemptUsage(1000, 400))
        on_attempt(2, [], AttemptUsage(1200, 600))
        return SCRIPT

    monkeypatch.setattr(run, "write_script", fake_write)
    code = run.main(
        [
            "--ticker", "^GSPC", "--condition", "down-weeks", "--n", "3",
            "--start", "2000-01-01", "--outdir", str(tmp_path),
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "시도 1: 위반 1건 (입력 1,000 / 출력 400 토큰)" in out
    assert "시도 2: 위반 0건 (입력 1,200 / 출력 600 토큰)" in out
    assert "입력 2,200 / 출력 1,000" in out
    assert "추정 $" in out


def test_failure_still_prints_what_it_spent(stub_market, tmp_path, capsys, monkeypatch):
    def fail(block, on_attempt=None):
        raise ScriptGenerationError(
            ["금지어 사용: 폭락"], 3, [AttemptUsage(1000, 500)] * 3
        )

    monkeypatch.setattr(run, "write_script", fail)
    code = run.main(
        [
            "--ticker", "^GSPC", "--condition", "down-weeks", "--n", "3",
            "--start", "2000-01-01", "--outdir", str(tmp_path),
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert list(tmp_path.glob("*_script.md")) == []
    assert "입력 3,000 / 출력 1,500" in out
    assert "추정 $" in out


def test_block_only_reports_no_usage(stub_market, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(run, "write_script", lambda *a, **k: pytest.fail("호출되면 안 된다"))
    run.main(
        [
            "--ticker", "^GSPC", "--condition", "down-weeks", "--n", "3",
            "--start", "2000-01-01", "--outdir", str(tmp_path), "--block-only",
        ]
    )
    assert "토큰" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "value,expected",
    [
        ("", "설정되지 않았다"),
        ("\x1b[200~sk-ant-api03-abc\x1b[201~", "제어문자"),
        ("sk-ant-api03-abc ", "제어문자"),
        ("복사가-잘못된-값", "sk-ant- 로 시작하지 않는다"),
    ],
)
def test_check_api_key_rejects_broken_values(value, expected):
    assert expected in run.check_api_key({run.KEY_ENV: value})


def test_check_api_key_accepts_a_normal_key():
    assert run.check_api_key({run.KEY_ENV: "sk-ant-api03-abc123"}) is None


def test_pasted_escape_codes_stop_before_any_api_call(monkeypatch, tmp_path, capsys):
    """붙여넣기로 깨진 키는 호출 전에 잡는다. 원인 모를 400 을 받지 않는다."""
    monkeypatch.setattr(run.me, "fetch_close", lambda *a, **k: falling_close())
    monkeypatch.setenv(run.KEY_ENV, "\x1b[200~sk-ant-api03-abc\x1b[201~")
    monkeypatch.setattr(run, "write_script", lambda *a, **k: pytest.fail("호출되면 안 된다"))
    code = run.main(
        [
            "--ticker", "^GSPC", "--condition", "down-weeks", "--n", "3",
            "--start", "2000-01-01", "--outdir", str(tmp_path),
        ]
    )
    assert code == 2
    assert list(tmp_path.glob("*_script.md")) == []
    assert len(list(tmp_path.glob("*_block.txt"))) == 1, "블록은 남아 있어야 한다"
    assert "제어문자" in capsys.readouterr().out


def test_api_failure_is_reported_readably(stub_market, tmp_path, capsys, monkeypatch):
    def boom(block, on_attempt=None):
        raise APICallError("API 호출 실패 (HTTP 400)\n크레딧 잔액이 0이거나...")

    monkeypatch.setattr(run, "write_script", boom)
    code = run.main(
        [
            "--ticker", "^GSPC", "--condition", "down-weeks", "--n", "3",
            "--start", "2000-01-01", "--outdir", str(tmp_path),
        ]
    )
    out = capsys.readouterr().out
    assert code == 3
    assert "HTTP 400" in out
    assert list(tmp_path.glob("*_script.md")) == []


def test_saved_script_carries_the_operator_guide(stub_market, tmp_path, monkeypatch):
    monkeypatch.setattr(run, "write_script", lambda block, on_attempt=None: SCRIPT)
    run.main(
        [
            "--ticker", "^GSPC", "--condition", "down-weeks", "--n", "3",
            "--start", "2000-01-01", "--outdir", str(tmp_path),
        ]
    )
    saved = list(tmp_path.glob("*_script.md"))[0].read_text(encoding="utf-8")
    assert run.OPERATOR_HEADER in saved, "제목 줄은 그대로 남아야 한다"
    assert "운영자 본인의 관점" in saved
    assert saved.count(run.OPERATOR_HEADER) == 1


def test_saved_script_still_passes_validation():
    """안내를 넣어도 저장본을 다시 검사했을 때 통과해야 한다."""
    from src.validator import validate
    from tests.fixtures import BLOCK

    assert validate(run.add_operator_guide(SCRIPT), BLOCK) == []


def test_guide_is_skipped_when_the_header_is_missing():
    assert run.add_operator_guide("헤더 없는 글") == "헤더 없는 글"
