"""데이터 블록을 넘겨 대본을 받고, 코드 검증을 통과할 때까지만 재시도한다."""

from collections import namedtuple
from pathlib import Path

from src.validator import validate

MODEL = "claude-sonnet-5"
MAX_TOKENS = 8000
MAX_ATTEMPTS = 3
FEEDBACK_HEADER = "[이전 시도에서 적발된 위반 — 이번엔 반드시 고친다]"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "script.md"

# USD / 100만 토큰. 2026-06-24 기준 공개 요금이며 바뀔 수 있다.
# 실제 청구액은 Anthropic 콘솔이 기준이고, 여기 값은 실행 중 참고용 추정치다.
# 요금이 바뀌면 이 표만 고치면 된다.
PRICE_PER_MTOK = {
    "claude-sonnet-5": {"input": 2.0, "output": 10.0},
    "claude-opus-5": {"input": 5.0, "output": 25.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
}

AttemptUsage = namedtuple("AttemptUsage", "input_tokens output_tokens")


class ScriptGenerationError(RuntimeError):
    """검증을 통과한 대본을 만들지 못했다. 이 경우 대본을 저장하지 않는다."""

    def __init__(self, violations, attempts, usages=None):
        self.violations = violations
        self.attempts = attempts
        # 실패해도 토큰은 이미 썼다. 얼마 나갔는지 알 수 있어야 한다.
        self.usages = list(usages or [])
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


def _usage(response):
    """응답에서 실제 토큰 사용량을 읽는다. 없으면 0으로 둔다."""
    usage = getattr(response, "usage", None)
    return AttemptUsage(
        int(getattr(usage, "input_tokens", 0) or 0),
        int(getattr(usage, "output_tokens", 0) or 0),
    )


def estimate_cost_usd(usages, model=MODEL):
    """추정 비용(USD). 요금표에 없는 모델이면 None."""
    price = PRICE_PER_MTOK.get(model)
    if price is None:
        return None
    total_in = sum(u.input_tokens for u in usages)
    total_out = sum(u.output_tokens for u in usages)
    return (total_in * price["input"] + total_out * price["output"]) / 1_000_000


def format_usage(usages, model=MODEL):
    """토큰 사용량 한 줄 요약. 실제 청구액이 아니라 추정치임을 밝힌다."""
    total_in = sum(u.input_tokens for u in usages)
    total_out = sum(u.output_tokens for u in usages)
    line = (
        f"토큰 {len(usages)}회 누적 — 입력 {total_in:,} / 출력 {total_out:,}"
    )
    cost = estimate_cost_usd(usages, model)
    if cost is not None:
        line += f" | 추정 ${cost:.4f} ({model} 요금표 기준, 실제 청구액은 콘솔 확인)"
    return line


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
    usages = []
    for attempt in range(1, max_attempts + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": build_user_message(block, violations)}],
        )
        script = _response_text(response)
        usages.append(_usage(response))
        violations = validate(script, block)
        if on_attempt is not None:
            on_attempt(attempt, violations, usages[-1])
        if not violations:
            return script

    raise ScriptGenerationError(violations, max_attempts, usages)
