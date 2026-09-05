"""데이터 블록을 넘겨 대본을 받고, 코드 검증을 통과할 때까지만 재시도한다."""

from pathlib import Path

from src.validator import validate

MODEL = "claude-sonnet-5"
MAX_TOKENS = 8000
MAX_ATTEMPTS = 3
FEEDBACK_HEADER = "[이전 시도에서 적발된 위반 — 이번엔 반드시 고친다]"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "script.md"


class ScriptGenerationError(RuntimeError):
    """검증을 통과한 대본을 만들지 못했다. 이 경우 대본을 저장하지 않는다."""

    def __init__(self, violations, attempts):
        self.violations = violations
        self.attempts = attempts
        joined = "\n".join(f"  - {v}" for v in violations)
        super().__init__(f"{attempts}회 시도 모두 검증 실패. 마지막 위반:\n{joined}")


def load_system_prompt(path=PROMPT_PATH):
    return Path(path).read_text(encoding="utf-8")


def build_user_message(block, violations=None):
    parts = [
        "아래 데이터 블록만 근거로 유튜브 롱폼 대본을 작성한다.",
        "블록에 없는 수치·날짜는 한 개도 쓰지 않는다.",
        "",
        block,
    ]
    if violations:
        # 추상적으로 "형식이 틀렸다"고 하면 다음 시도도 똑같이 틀린다.
        # 적발된 문구를 그대로 되먹여야 통과율이 오른다.
        parts += ["", FEEDBACK_HEADER]
        parts += [f"- {v}" for v in violations]
    return "\n".join(parts)


def _response_text(response):
    return "".join(
        block.text
        for block in response.content
        if getattr(block, "type", "text") == "text"
    )


def write_script(
    block,
    client=None,
    system_prompt=None,
    max_attempts=MAX_ATTEMPTS,
    on_attempt=None,
):
    """검증을 통과한 대본을 돌려준다. 못 만들면 ScriptGenerationError."""
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    system = load_system_prompt() if system_prompt is None else system_prompt

    violations = []
    for attempt in range(1, max_attempts + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": build_user_message(block, violations)}],
        )
        script = _response_text(response)
        violations = validate(script, block)
        if on_attempt is not None:
            on_attempt(attempt, violations)
        if not violations:
            return script

    raise ScriptGenerationError(violations, max_attempts)
