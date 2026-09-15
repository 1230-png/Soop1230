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


def test_a_failure_shows_stdout_too(monkeypatch):
    """claude 는 실패 사유를 stdout 으로 내기도 한다. stderr 만 찍으면 원인을 못 찾는다."""
    monkeypatch.setattr(
        cli_client.subprocess, "run",
        lambda argv, **k: fake_completed(
            stdout="Invalid API key · Please run /login", returncode=1, stderr=""
        ),
    )
    with pytest.raises(cli_client.CliClientError, match="Invalid API key"):
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


def test_a_stale_api_key_cannot_hijack_the_subscription(monkeypatch):
    """죽은 키가 환경에 남아 있으면 claude 가 구독 대신 그 키를 쓰고 조용히 실패한다."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-잔액없는키")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "토큰")
    seen = {}

    def fake_run(argv, **kwargs):
        seen["env"] = kwargs.get("env")
        return fake_completed(payload())

    monkeypatch.setattr(cli_client.subprocess, "run", fake_run)
    cli_client.ClaudeCliClient().messages.create(messages=[{"role": "user", "content": "x"}])
    assert "ANTHROPIC_API_KEY" not in seen["env"]
    assert "ANTHROPIC_AUTH_TOKEN" not in seen["env"]
    # 나머지 환경은 그대로여야 한다. PATH 가 없으면 claude 를 찾지 못한다.
    assert "PATH" in seen["env"]


def test_check_cli_also_ignores_a_stale_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-잔액없는키")
    seen = {}

    def fake_run(argv, **kwargs):
        seen["env"] = kwargs.get("env")
        return fake_completed("2.1.272")

    monkeypatch.setattr(cli_client.subprocess, "run", fake_run)
    assert cli_client.check_cli() is None
    assert "ANTHROPIC_API_KEY" not in seen["env"]


def test_the_command_is_resolved_through_pathext(monkeypatch):
    """윈도우 npm 전역 설치는 claude.cmd 다. subprocess 는 PATHEXT 를 보지 않는다."""
    monkeypatch.setattr(
        cli_client.shutil, "which", lambda name: r"C:\Users\admin\AppData\Roaming\npm\claude.cmd"
    )
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return fake_completed(payload())

    monkeypatch.setattr(cli_client.subprocess, "run", fake_run)
    cli_client.ClaudeCliClient().messages.create(messages=[{"role": "user", "content": "x"}])
    assert seen["argv"][0].endswith("claude.cmd")


def test_an_unresolvable_command_falls_back_to_the_bare_name(monkeypatch):
    """찾지 못하면 그대로 넘겨서 FileNotFoundError 와 안내 문구가 나오게 둔다."""
    monkeypatch.setattr(cli_client.shutil, "which", lambda name: None)
    assert cli_client.resolve_command("claude") == "claude"


def test_a_failure_pulls_the_reason_out_of_the_result_json(monkeypatch):
    """실패 JSON 을 통째로 자르면 사유가 담긴 뒤쪽이 날아간다. 필드를 뽑아낸다."""
    big = json.dumps({
        "usage": {"input_tokens": 0, "x": "가" * 900},
        "terminal_reason": "api_error",
        "subtype": "error_during_execution",
        "result": "OAuth token is invalid or expired",
    })
    monkeypatch.setattr(
        cli_client.subprocess, "run",
        lambda argv, **k: fake_completed(stdout=big, returncode=1),
    )
    with pytest.raises(cli_client.CliClientError) as caught:
        cli_client.ClaudeCliClient().messages.create(messages=[{"role": "user", "content": "x"}])
    message = str(caught.value)
    assert "OAuth token is invalid or expired" in message
    assert "api_error" in message


def test_the_token_is_trimmed_before_it_reaches_claude(monkeypatch):
    """시크릿에 붙여넣을 때 앞뒤 공백·줄바꿈·따옴표가 딸려 들어가기 쉽다."""
    monkeypatch.setenv(cli_client.OAUTH_ENV, '  "sk-ant-oat01-값"\n')
    seen = {}

    def fake_run(argv, **kwargs):
        seen["env"] = kwargs.get("env")
        return fake_completed(payload())

    monkeypatch.setattr(cli_client.subprocess, "run", fake_run)
    cli_client.ClaudeCliClient().messages.create(messages=[{"role": "user", "content": "x"}])
    assert seen["env"][cli_client.OAUTH_ENV] == "sk-ant-oat01-값"


def test_check_token_catches_a_truncated_paste():
    assert "잘린" in cli_client.check_token("sk-ant-oat01-tooshort")


def test_check_token_catches_non_ascii():
    assert "ASCII" in cli_client.check_token("sk-ant-oat01-한글섞임" + "x" * 90)


def test_check_token_does_not_judge_the_prefix():
    """접두사는 발급하는 쪽 사정이다. 확인하지 않은 규칙으로 막으면 멀쩡한 토큰이 튕긴다."""
    assert cli_client.check_token("anything-" + "x" * 90) is None


def test_check_token_accepts_a_full_token():
    assert cli_client.check_token("sk-ant-oat01-" + "x" * 90) is None


def test_check_token_is_quiet_without_a_token():
    """로컬은 로그인으로 돈다. 토큰이 없다고 막으면 안 된다."""
    assert cli_client.check_token(None) is None
    assert cli_client.check_token("") is None
