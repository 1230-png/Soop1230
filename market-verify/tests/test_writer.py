import pytest

from src.writer import (
    FEEDBACK_HEADER,
    MAX_TOKENS,
    MODEL,
    ScriptGenerationError,
    build_user_message,
    load_system_prompt,
    write_script,
)
from tests.fixtures import BLOCK, SCRIPT


class FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeBlock(text)]


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
        on_attempt=lambda attempt, violations: seen.append((attempt, len(violations))),
    )
    assert [a for a, _ in seen] == [1, 2]
    assert seen[0][1] > 0
    assert seen[1][1] == 0


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
