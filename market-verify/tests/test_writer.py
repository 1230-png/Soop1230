import pytest

from src.writer import (
    FEEDBACK_HEADER,
    MAX_TOKENS,
    MODEL,
    PRICE_PER_MTOK,
    ScriptGenerationError,
    build_user_message,
    estimate_cost_usd,
    format_usage,
    load_system_prompt,
    write_script,
)
from tests.fixtures import BLOCK, SCRIPT


class FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeUsage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class FakeResponse:
    def __init__(self, text, input_tokens=1000, output_tokens=500):
        self.content = [FakeBlock(text)]
        self.usage = FakeUsage(input_tokens, output_tokens)


class FakeMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(self.replies.pop(0))


class FakeClient:
    """API를 때리지 않고 재시도 흐름만 검증한다."""

    def __init__(self, replies):
        self.messages = FakeMessages(replies)


BROKEN = SCRIPT.replace("상승비율은 58.3입니다", "상승비율은 73.9로 급등했습니다")


def test_system_prompt_file_loads_with_hard_rules():
    prompt = load_system_prompt()
    assert "# Hard Rules" in prompt
    assert "## 6. [운영자 코멘트]" in prompt


def test_first_attempt_success_makes_one_call():
    client = FakeClient([SCRIPT])
    assert write_script(BLOCK, client=client, system_prompt="sys") == SCRIPT
    assert len(client.messages.calls) == 1


def test_request_uses_configured_model_and_system_prompt():
    client = FakeClient([SCRIPT])
    write_script(BLOCK, client=client, system_prompt="시스템 프롬프트 전문")
    call = client.messages.calls[0]
    assert call["model"] == MODEL
    assert call["max_tokens"] == MAX_TOKENS
    assert call["system"] == "시스템 프롬프트 전문"
    assert BLOCK in call["messages"][0]["content"]


def test_first_attempt_carries_no_feedback_block():
    client = FakeClient([SCRIPT])
    write_script(BLOCK, client=client, system_prompt="sys")
    assert FEEDBACK_HEADER not in client.messages.calls[0]["messages"][0]["content"]


def test_retry_feeds_back_the_exact_violations():
    client = FakeClient([BROKEN, SCRIPT])
    assert write_script(BLOCK, client=client, system_prompt="sys") == SCRIPT
    assert len(client.messages.calls) == 2
    retry_body = client.messages.calls[1]["messages"][0]["content"]
    assert FEEDBACK_HEADER in retry_body
    assert "금지어 사용: 급등" in retry_body
    assert "데이터 블록에 없는 숫자: 73.9" in retry_body


def test_three_failures_raise_and_return_no_script():
    client = FakeClient([BROKEN, BROKEN, BROKEN])
    with pytest.raises(ScriptGenerationError) as excinfo:
        write_script(BLOCK, client=client, system_prompt="sys")
    assert len(client.messages.calls) == 3
    assert excinfo.value.attempts == 3
    assert any("급등" in v for v in excinfo.value.violations)


def test_never_calls_more_than_max_attempts():
    client = FakeClient([BROKEN] * 3)
    with pytest.raises(ScriptGenerationError):
        write_script(BLOCK, client=client, system_prompt="sys")
    assert client.messages.calls, "요청이 한 번도 나가지 않았다"
    assert len(client.messages.calls) == 3


def test_on_attempt_callback_reports_each_round():
    seen = []
    client = FakeClient([BROKEN, SCRIPT])
    write_script(
        BLOCK,
        client=client,
        system_prompt="sys",
        on_attempt=lambda attempt, violations, usage: seen.append(
            (attempt, len(violations), usage.output_tokens)
        ),
    )
    assert [a for a, _, _ in seen] == [1, 2]
    assert seen[0][1] > 0
    assert seen[1][1] == 0
    assert all(tokens == 500 for _, _, tokens in seen)


def test_multiple_text_blocks_are_joined():
    class SplitClient:
        class messages:
            calls = []

            @staticmethod
            def create(**kwargs):
                SplitClient.messages.calls.append(kwargs)
                response = FakeResponse("")
                half = len(SCRIPT) // 2
                response.content = [FakeBlock(SCRIPT[:half]), FakeBlock(SCRIPT[half:])]
                return response

    assert write_script(BLOCK, client=SplitClient, system_prompt="sys") == SCRIPT


def test_build_user_message_lists_violations_verbatim():
    body = build_user_message(BLOCK, ["금지어 사용: 폭락", "필수 헤더 누락: ## 4. 결과"])
    assert "- 금지어 사용: 폭락" in body
    assert "- 필수 헤더 누락: ## 4. 결과" in body


def test_usage_is_reported_for_every_attempt():
    seen = []
    client = FakeClient([BROKEN, SCRIPT])
    write_script(
        BLOCK,
        client=client,
        system_prompt="sys",
        on_attempt=lambda attempt, violations, usage: seen.append(usage),
    )
    assert len(seen) == 2
    assert [u.input_tokens for u in seen] == [1000, 1000]
    assert [u.output_tokens for u in seen] == [500, 500]


def test_failed_run_still_reports_what_it_spent():
    """3회 실패해도 토큰은 나갔다. 얼마 썼는지 알 수 있어야 한다."""
    client = FakeClient([BROKEN, BROKEN, BROKEN])
    with pytest.raises(ScriptGenerationError) as excinfo:
        write_script(BLOCK, client=client, system_prompt="sys")
    usages = excinfo.value.usages
    assert len(usages) == 3
    assert sum(u.output_tokens for u in usages) == 1500


def test_missing_usage_field_does_not_crash():
    """usage 를 주지 않는 응답에도 죽지 않아야 한다."""

    class NoUsageClient:
        class messages:
            @staticmethod
            def create(**kwargs):
                response = FakeResponse(SCRIPT)
                del response.usage
                return response

    seen = []
    write_script(
        BLOCK,
        client=NoUsageClient,
        system_prompt="sys",
        on_attempt=lambda a, v, u: seen.append(u),
    )
    assert seen[0].input_tokens == 0
    assert seen[0].output_tokens == 0


def test_cost_estimate_uses_the_price_table():
    from src.writer import AttemptUsage

    usages = [AttemptUsage(1_000_000, 1_000_000)]
    price = PRICE_PER_MTOK[MODEL]
    assert estimate_cost_usd(usages, MODEL) == pytest.approx(
        price["input"] + price["output"]
    )


def test_cost_estimate_is_none_for_unknown_model():
    from src.writer import AttemptUsage

    assert estimate_cost_usd([AttemptUsage(10, 10)], "some-unlisted-model") is None


def test_format_usage_shows_totals_and_flags_the_estimate():
    from src.writer import AttemptUsage

    line = format_usage([AttemptUsage(1000, 500), AttemptUsage(2000, 800)], MODEL)
    assert "2회 누적" in line
    assert "3,000" in line
    assert "1,300" in line
    assert "추정" in line and "콘솔" in line


def test_format_usage_omits_cost_for_unknown_model():
    from src.writer import AttemptUsage

    line = format_usage([AttemptUsage(1000, 500)], "some-unlisted-model")
    assert "추정" not in line
