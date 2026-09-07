import pandas as pd
import pytest

from src import run_tokenomics, tokenomics
from src.writer import AttemptUsage, ScriptGenerationError


def chart(days=1500):
    start = pd.Timestamp("2015-01-01")
    prices, caps = [], []
    for i in range(days):
        ms = int((start + pd.Timedelta(days=i)).timestamp() * 1000)
        price = 100.0 + i * 0.4
        prices.append([ms, price])
        caps.append([ms, price * (1000.0 + i * 0.5)])
    return {"prices": prices, "market_caps": caps}


@pytest.fixture
def stub_coingecko(monkeypatch):
    payload = chart()
    # 패치 대상과 같은 함수를 안에서 부르면 무한 재귀가 된다. 원본을 먼저 잡아 둔다.
    real_fetch = tokenomics.fetch_market_chart

    def stubbed(coin_id, days="max", fetcher=None):
        return real_fetch(coin_id, fetcher=lambda cid, params: payload)

    monkeypatch.setattr(run_tokenomics.tokenomics, "fetch_market_chart", stubbed)
    monkeypatch.setenv(run_tokenomics.KEY_ENV, "sk-ant-test-key")


def test_dilution_needs_a_coin_id():
    with pytest.raises(SystemExit):
        run_tokenomics.parse_args(["--mode", "dilution", "--asset", "비트코인"])


def test_epochs_must_be_positive():
    with pytest.raises(SystemExit):
        run_tokenomics.parse_args(["--asset", "비트코인", "--epochs", "0"])


def test_schedule_mode_needs_no_network(tmp_path, capsys, monkeypatch):
    """발행 스케줄은 합의 규칙에서 나온다. 아무것도 받아오지 않는다."""
    monkeypatch.setattr(
        run_tokenomics.tokenomics,
        "fetch_market_chart",
        lambda *a, **k: pytest.fail("스케줄 모드는 데이터를 받으면 안 된다"),
    )
    code = run_tokenomics.main(
        ["--mode", "schedule", "--asset", "비트코인",
         "--outdir", str(tmp_path), "--block-only"]
    )
    assert code == 0
    block = list(tmp_path.glob("*_block.txt"))[0].read_text(encoding="utf-8")
    assert "21,000,000.00" in block
    assert "외부 데이터 없음" in block
    assert "수렴 총 발행량" in capsys.readouterr().out


def test_schedule_filename_records_the_epoch_count(tmp_path):
    run_tokenomics.main(
        ["--mode", "schedule", "--asset", "비트코인", "--epochs", "6",
         "--outdir", str(tmp_path), "--block-only"]
    )
    assert list(tmp_path.glob("*_schedule6_*_block.txt"))


def test_dilution_mode_writes_a_block(stub_coingecko, tmp_path, capsys):
    code = run_tokenomics.main(
        ["--mode", "dilution", "--coin", "bitcoin", "--asset", "비트코인",
         "--outdir", str(tmp_path), "--block-only"]
    )
    assert code == 0
    block = list(tmp_path.glob("*_block.txt"))[0].read_text(encoding="utf-8")
    assert "코인 ID: bitcoin" in block
    assert "CoinGecko" in block
    assert "유통량 증가율" in capsys.readouterr().out


def test_coingecko_failure_is_reported_without_a_traceback(tmp_path, capsys, monkeypatch):
    def boom(*a, **k):
        raise tokenomics.TokenomicsError("코인 ID 를 확인할 것")

    monkeypatch.setattr(run_tokenomics.tokenomics, "fetch_market_chart", boom)
    code = run_tokenomics.main(
        ["--mode", "dilution", "--coin", "nope", "--asset", "X",
         "--outdir", str(tmp_path)]
    )
    assert code == 3
    assert "코인 ID 를 확인할 것" in capsys.readouterr().out


def test_broken_anthropic_key_stops_after_the_block(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv(run_tokenomics.KEY_ENV, "\x1b[200~sk-ant-abc\x1b[201~")
    monkeypatch.setattr(
        run_tokenomics, "write_script", lambda *a, **k: pytest.fail("호출되면 안 된다")
    )
    code = run_tokenomics.main(
        ["--mode", "schedule", "--asset", "비트코인", "--outdir", str(tmp_path)]
    )
    assert code == 2
    assert len(list(tmp_path.glob("*_block.txt"))) == 1
    assert "제어문자" in capsys.readouterr().out


def test_success_saves_the_script_with_the_operator_guide(tmp_path, monkeypatch):
    from tests.fixtures import SCRIPT

    monkeypatch.setenv(run_tokenomics.KEY_ENV, "sk-ant-test-key")
    monkeypatch.setattr(
        run_tokenomics, "write_script", lambda block, on_attempt=None: SCRIPT
    )
    code = run_tokenomics.main(
        ["--mode", "schedule", "--asset", "비트코인", "--outdir", str(tmp_path)]
    )
    assert code == 0
    saved = list(tmp_path.glob("*_script.md"))[0].read_text(encoding="utf-8")
    assert "운영자 본인의 관점" in saved


def test_failure_saves_no_script_but_reports_the_spend(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv(run_tokenomics.KEY_ENV, "sk-ant-test-key")

    def fail(block, on_attempt=None):
        raise ScriptGenerationError(["금지어 사용: 폭락"], 3, [AttemptUsage(1000, 500)] * 3)

    monkeypatch.setattr(run_tokenomics, "write_script", fail)
    code = run_tokenomics.main(
        ["--mode", "schedule", "--asset", "비트코인", "--outdir", str(tmp_path)]
    )
    assert code == 1
    assert list(tmp_path.glob("*_script.md")) == []
    assert "입력 3,000 / 출력 1,500" in capsys.readouterr().out
