"""ANTHROPIC_API_KEY 없이, 이미 깔려 있는 Claude Code(`claude -p`)로 대본을 받는다.

`writer.write_script()` 는 클라이언트를 갈아끼울 수 있게 돼 있다. 이 어댑터가
anthropic SDK 응답과 같은 모양으로 돌려주므로 검증·재시도 루프는 손대지 않는다.

**API 크레딧 대신 구독 사용량을 쓴다.** 무인으로 돌리면 그만큼 평소 쓰는 한도를
깎아먹는다는 뜻이다. 대본 한 편이 큰 양은 아니지만 공짜는 아니다.

데이터 블록은 수 KB 라서 명령줄 인자로 넘기지 않는다 — 윈도우는 명령줄이
약 8191자에서 잘린다. 표준입력으로 넣는다.
"""

import json
import subprocess
import tempfile
from pathlib import Path

DEFAULT_COMMAND = "claude"
DEFAULT_TIMEOUT = 900
# 대본만 받으면 된다. 무인으로 도는 자리라 도구를 열어 둘 이유가 없다.
BLOCKED_TOOLS = (
    "Bash,Read,Write,Edit,NotebookEdit,Glob,Grep,WebFetch,WebSearch,Task,Agent"
)


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
                self.command, "-p",
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
                encoding="utf-8", timeout=self.timeout,
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
            [command, "--version"], capture_output=True, text=True, timeout=60
        )
    except FileNotFoundError:
        return (
            f"'{command}' 를 찾지 못했다. Claude Code 를 깔고 PATH 에 넣을 것:\n"
            "  npm install -g @anthropic-ai/claude-code\n"
            "  깐 뒤 `claude` 를 한 번 실행해 로그인해 둘 것."
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        return f"'{command} --version' 이 응답하지 않는다: {error}"
    if done.returncode != 0:
        return f"'{command} --version' 이 종료코드 {done.returncode} 로 끝났다."
    return None
