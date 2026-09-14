import json
import subprocess

import pytest

from src import cli_client, run, writer


def fake_completed(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=["claude"], returncode=returncode,
                                       stdout=stdout, stderr=stderr)


def payload(result="대본", input_tokens=11, output_tokens=22, **extra):
    body = {
        "result": result,
        "is_error": False,
        "stop_reason": "end_turn",
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }
    body.update(extra)
    return json.dumps(body)


@pytest.fixture
def spy(monkeypatch):
    """subprocess 호출을 가로챈다. 실제 claude 를 부르지 않는다."""
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["input"] = kwargs.get("input")
        return fake_completed(payload())

    monkeypatch.setattr(cli_client.subprocess, "run", fake_run)
    return seen


def test_response_looks_like_the_sdk_response(spy):
    response = cli_client.ClaudeCliClient().messages.create(
        model="claude-sonnet-5", max_tokens=100, system="시스템",
        messages=[{"role": "user", "content": "블록"}],
    )
    assert response.content[0].text == "대본"
    assert response.content[0].type == "text"
    assert response.usage.input_tokens == 11
    assert response.usage.output_tokens == 22
    assert response.stop_reason == "end_turn"


def test_the_block_goes_through_stdin_not_the_command_line(spy):
    """윈도우 명령줄은 약 8191자에서 잘린다. 블록은 그보다 길 수 있다."""
    long_block = "가" * 20000
    cli_client.ClaudeCliClient().messages.create(
        messages=[{"role": "user", "content": long_block}]
    )
    assert spy["input"] == long_block
    assert not any(long_block in str(part) for part in spy["argv"])


def test_the_model_and_tool_limits_are_passed(spy):
    cli_client.ClaudeCliClient().messages.create(
        model="claude-sonnet-5", system="시스템", messages=[{"role": "user", "content": "x"}]
    )
    argv = spy["argv"]
    assert "-p" in argv and "--output-format" in argv
    assert argv[argv.index("--model") + 1] == "claude-sonnet-5"
    assert "--system-prompt-file" in argv
    assert "Bash" in argv[argv.index("--disallowedTools") + 1]


def test_a_nonzero_exit_says_to_check_the_login(monkeypatch):
    monkeypatch.setattr(
        cli_client.subprocess, "run",
        lambda argv, **k: fake_completed(returncode=1, stderr="not logged in"),
    )
    with pytest.raises(cli_client.CliClientError, match="로그인"):
        cli_client.ClaudeCliClient().messages.create(messages=[{"role": "user", "content": "x"}])


def test_unreadable_output_is_reported(monkeypatch):
    monkeypatch.setattr(
        cli_client.subprocess, "run", lambda argv, **k: fake_completed(stdout="JSON 아님")
    )
    with pytest.raises(cli_client.CliClientError, match="JSON"):
        cli_client.ClaudeCliClient().messages.create(messages=[{"role": "user", "content": "x"}])


def test_an_error_payload_is_reported(monkeypatch):
    monkeypatch.setattr(
        cli_client.subprocess, "run",
        lambda argv, **k: fake_completed(payload(result="한도 초과", is_error=True)),
    )
    with pytest.raises(cli_client.CliClientError, match="한도 초과"):
        cli_client.ClaudeCliClient().messages.create(messages=[{"role": "user", "content": "x"}])


def test_a_missing_claude_tells_you_how_to_install_it(monkeypatch):
    def explode(argv, **kwargs):
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(cli_client.subprocess, "run", explode)
    with pytest.raises(cli_client.CliClientError, match="npm install"):
        cli_client.ClaudeCliClient().messages.create(messages=[{"role": "user", "content": "x"}])


def test_a_timeout_is_reported(monkeypatch):
    def explode(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1)

    monkeypatch.setattr(cli_client.subprocess, "run", explode)
    with pytest.raises(cli_client.CliClientError, match="끝나지 않았다"):
        cli_client.ClaudeCliClient().messages.create(messages=[{"role": "user", "content": "x"}])


def test_check_cli_is_quiet_when_claude_answers(monkeypatch):
    monkeypatch.setattr(cli_client.subprocess, "run", lambda argv, **k: fake_completed("2.0.0"))
    assert cli_client.check_cli() is None


def test_check_cli_says_how_to_install_when_missing(monkeypatch):
    def explode(argv, **kwargs):
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(cli_client.subprocess, "run", explode)
    assert "npm install" in cli_client.check_cli()


# --- 스위치 (writer / run 쪽) ---

def test_uses_cli_reads_the_switch():
    assert writer.uses_cli({writer.CLIENT_ENV: "cli"}) is True
    assert writer.uses_cli({writer.CLIENT_ENV: "CLI"}) is True
    assert writer.uses_cli({writer.CLIENT_ENV: "api"}) is False
    assert writer.uses_cli({}) is False


def test_default_client_follows_the_switch():
    assert isinstance(
        writer.default_client({writer.CLIENT_ENV: "cli"}), cli_client.ClaudeCliClient
    )


def test_cli_mode_checks_claude_instead_of_the_api_key(monkeypatch):
    """구독 모드에서는 키가 없어도 막지 않는다. 대신 claude 가 있는지 본다."""
    monkeypatch.setattr(cli_client, "check_cli", lambda command=None: None)
    assert run.check_api_key({writer.CLIENT_ENV: "cli"}) is None
    # 스위치가 없으면 예전대로 키를 본다.
    assert "설정되지 않았다" in run.check_api_key({})


def test_a_cli_failure_becomes_an_api_call_error(monkeypatch):
    """무인 실행에서 스택트레이스만 남지 않게, 키 실패와 같은 층으로 묶는다."""
    class Boom:
        class messages:
            @staticmethod
            def create(**kwargs):
                raise cli_client.CliClientError("로그인이 풀렸다")

    with pytest.raises(writer.APICallError, match="로그인이 풀렸다"):
        writer.write_script("블록", client=Boom(), system_prompt="시스템")


def test_usage_line_does_not_claim_a_charge_in_cli_mode():
    """구독 모드에서 '추정 $0.08' 만 찍으면 API 청구가 난 줄 안다."""
    usages = [writer.AttemptUsage(100, 2000)]
    cli_line = writer.format_usage(usages, env={writer.CLIENT_ENV: "cli"})
    assert "API 청구 없음" in cli_line
    api_line = writer.format_usage(usages, env={})
    assert "추정 $" in api_line and "API 청구 없음" not in api_line
