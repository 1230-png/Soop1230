"""ANTHROPIC_API_KEY 없이, 이미 깔려 있는 Claude Code(`claude -p`)로 대본을 받는다.

`writer.write_script()` 는 클라이언트를 갈아끼울 수 있게 돼 있다. 이 어댑터가
anthropic SDK 응답과 같은 모양으로 돌려주므로 검증·재시도 루프는 손대지 않는다.

**API 크레딧 대신 구독 사용량을 쓴다.** 무인으로 돌리면 그만큼 평소 쓰는 한도를
깎아먹는다는 뜻이다. 대본 한 편이 큰 양은 아니지만 공짜는 아니다.

데이터 블록은 수 KB 라서 명령줄 인자로 넘기지 않는다 — 윈도우는 명령줄이
약 8191자에서 잘린다. 표준입력으로 넣는다.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_COMMAND = "claude"
DEFAULT_TIMEOUT = 900
# 대본만 받으면 된다. 무인으로 도는 자리라 도구를 열어 둘 이유가 없다.
BLOCKED_TOOLS = (
    "Bash,Read,Write,Edit,NotebookEdit,Glob,Grep,WebFetch,WebSearch,Task,Agent"
)


# claude 는 이 변수들이 있으면 구독 로그인보다 그쪽을 먼저 쓴다.
# 크레딧이 0 인 옛날 키가 환경에 남아 있으면 "Credit balance is too low" 로
# 매번 조용히 실패한다. 무인으로 도는 자리라 이걸 사람이 알아채기 어렵다.
AUTH_ENV_TO_DROP = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_URL")


def _subscription_env():
    """구독 로그인을 가로채는 인증 변수를 뺀 환경을 만든다."""
    env = os.environ.copy()
    for name in AUTH_ENV_TO_DROP:
        env.pop(name, None)
    return env


def resolve_command(command=DEFAULT_COMMAND):
    """실행 파일의 실제 경로를 찾는다. 못 찾으면 이름을 그대로 돌려준다.

    윈도우에서 npm 전역 설치는 `claude.cmd` 를 만든다. 명령 프롬프트는 PATHEXT 를
    보고 확장자를 붙여 찾아주지만 subprocess 는 그러지 않아서, 터미널에서는 되는
    `claude` 가 파이썬에서만 "찾지 못했다" 로 끝난다. shutil.which 는 PATHEXT 를 본다.
    """
    return shutil.which(command) or command


class CliClientError(RuntimeError):
    """claude 실행 자체가 실패했다. 대본 내용 문제가 아니다."""


class _TextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Usage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _Response:
    """anthropic SDK 응답에서 writer 가 읽는 것만 흉내낸다."""

    def __init__(self, text, usage, stop_reason):
        self.content = [_TextBlock(text)]
        self.usage = usage
        self.stop_reason = stop_reason


class _Messages:
    def __init__(self, client):
        self._client = client

    def create(self, model=None, max_tokens=None, system=None, messages=None, **_):
        # max_tokens 는 받아만 두고 쓰지 않는다. claude -p 는 자체 상한을 쓴다
        # (sonnet 기준 SDK 기본 상한보다 커서, 대본이 잘리는 쪽으로는 안 간다).
        return self._client.complete(model=model, system=system, messages=messages)


class ClaudeCliClient:
    """`anthropic.Anthropic()` 자리에 그대로 끼운다."""

    def __init__(self, command=DEFAULT_COMMAND, timeout=DEFAULT_TIMEOUT):
        self.command = command
        self.timeout = timeout
        self.messages = _Messages(self)

    def complete(self, model=None, system=None, messages=None):
        prompt = "\n".join(
            message["content"]
            for message in (messages or [])
            if message.get("role") == "user"
        )
        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                resolve_command(self.command), "-p",
                "--output-format", "json",
                "--disallowedTools", BLOCKED_TOOLS,
            ]
            if model:
                argv += ["--model", model]
            if system:
                system_path = Path(tmp) / "system.md"
                system_path.write_text(system, encoding="utf-8")
                argv += ["--system-prompt-file", str(system_path)]
            done = self._run(argv, prompt)
        return self._parse(done)

    def _run(self, argv, prompt):
        try:
            return subprocess.run(
                argv, input=prompt, capture_output=True, text=True,
                encoding="utf-8", timeout=self.timeout, env=_subscription_env(),
            )
        except FileNotFoundError as error:
            raise CliClientError(
                f"'{self.command}' 를 찾지 못했다. Claude Code 가 깔려 있고 "
                "PATH 에 잡히는지 확인할 것: npm install -g @anthropic-ai/claude-code"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise CliClientError(
                f"{self.timeout}초 안에 끝나지 않았다. 대본이 길면 timeout 을 올릴 것."
            ) from error

    def _parse(self, done):
        if done.returncode != 0:
            raise CliClientError(
                f"claude 가 종료코드 {done.returncode} 로 끝났다.\n"
                f"  {(done.stderr or '').strip()[:500]}\n"
                "  로그인이 풀렸을 수 있다. 사람이 한 번 `claude` 를 실행해 확인할 것."
            )
        try:
            payload = json.loads(done.stdout)
        except (json.JSONDecodeError, TypeError) as error:
            raise CliClientError(
                f"claude 출력을 JSON 으로 읽지 못했다.\n  {(done.stdout or '')[:500]}"
            ) from error
        if payload.get("is_error"):
            raise CliClientError(
                f"claude 가 오류를 돌려줬다: {payload.get('result') or payload.get('subtype')}"
            )

        usage = payload.get("usage") or {}
        return _Response(
            payload.get("result") or "",
            _Usage(
                int(usage.get("input_tokens") or 0),
                int(usage.get("output_tokens") or 0),
            ),
            payload.get("stop_reason"),
        )


def check_cli(command=DEFAULT_COMMAND):
    """부르기 전에 claude 가 있는지 본다. 문제가 없으면 None.

    다 만들고 나서 없다고 하면 시간만 버린다 — 키 확인과 같은 이유다.
    """
    try:
        done = subprocess.run(
            [resolve_command(command), "--version"], capture_output=True, text=True,
            timeout=60, env=_subscription_env(),
        )
    except FileNotFoundError:
        return (
            f"'{command}' 를 찾지 못했다. Claude Code 를 깔고 PATH 에 넣을 것:\n"
            "  npm install -g @anthropic-ai/claude-code\n"
            "  깐 뒤 `claude` 를 한 번 실행해 로그인해 둘 것.\n"
            "  이미 깔았는데도 이 메시지가 나오면, 깔기 전에 열어 둔 창이라 PATH 가\n"
            "  갱신되지 않은 것이다. 창을 새로 열 것."
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        return f"'{command} --version' 이 응답하지 않는다: {error}"
    if done.returncode != 0:
        return f"'{command} --version' 이 종료코드 {done.returncode} 로 끝났다."
    return None
