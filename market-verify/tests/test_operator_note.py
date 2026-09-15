"""운영자 코멘트를 채우는 단계.

검증기는 **대본 작성 모델이** 이 칸을 채우면 위반으로 잡는다. 그 규칙은 여기서
건드리지 않는다 — 작성 루프가 자기 대본에 사람 목소리를 지어 넣는 것을 막는
규칙이고, 그건 그대로다. 여기 테스트는 검증이 끝난 뒤 덧붙이는 별도 단계를 본다.
"""

import pytest

from src import operator_note, validator
from tests.fixtures import SCRIPT

GOOD = "조건이 같아도 그다음이 같지는 않았다. 표본을 늘려도 그 점은 달라지지 않는다."


class FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeBlock(text)]


class FakeMessages:
    def __init__(self, text):
        self._text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(self._text)


class FakeClient:
    def __init__(self, text):
        self.messages = FakeMessages(text)


def test_check_passes_a_plain_comment():
    assert operator_note.check(GOOD) is None


def test_check_refuses_digits():
    """블록을 거치지 않은 숫자는 검증할 방법이 없다. 채널 규칙 그대로다."""
    assert "숫자" in operator_note.check("3주 연속이었다는 점이 눈에 남는다.")


@pytest.mark.parametrize("word", validator.BANNED_WORDS)
def test_check_refuses_every_banned_word(word):
    assert "금지어" in operator_note.check(f"이번 건은 {word} 이라고 느꼈다.")


@pytest.mark.parametrize(
    "text",
    [
        "앞으로 오를 것 같다는 생각이 든다.",
        "지금은 매수 구간이라고 본다.",
        "목표가를 정해 두는 편이 낫다.",
        "내릴 때를 기다리는 사람도 있다.",
    ],
)
def test_check_refuses_advice_and_prediction(text):
    """유사투자자문 규제. 운영자 코멘트라서 오히려 권유처럼 읽힌다."""
    assert "권유" in operator_note.check(text)


def test_check_refuses_an_overlong_comment():
    assert "너무 길다" in operator_note.check("가" * 300)


def test_check_refuses_nothing_at_all():
    assert operator_note.check("") is not None
    assert operator_note.check(None) is not None


def test_has_note_reads_the_empty_section_as_empty():
    assert operator_note.has_note(SCRIPT) is False


def test_has_note_ignores_a_rule_and_a_comment():
    """구분선과 HTML 주석은 사람이 쓴 코멘트가 아니다. 검증기와 같은 판단이다."""
    filled = SCRIPT.replace(
        operator_note.HEADER,
        operator_note.HEADER + "\n<!-- 여기에 소회를 적을 것 -->\n---",
        1,
    )
    assert operator_note.has_note(filled) is False


def test_insert_puts_the_comment_under_its_header():
    filled = operator_note.insert(SCRIPT, GOOD)
    assert operator_note.has_note(filled) is True
    body = filled.split(operator_note.HEADER, 1)[1].split("\n## ", 1)[0]
    assert body.strip() == GOOD


def test_fill_writes_a_comment_that_passes():
    filled = operator_note.fill(SCRIPT, client=FakeClient(GOOD), log=lambda *a: None)
    assert GOOD in filled


def test_fill_drops_a_comment_that_breaks_the_rules():
    """규칙을 어긴 문장은 버리고 칸을 비운 채로 간다. 멈추지는 않는다."""
    lines = []
    filled = operator_note.fill(
        SCRIPT, client=FakeClient("지금 당장 매수해야 한다."), log=lines.append
    )
    assert filled == SCRIPT
    assert any("버렸다" in line for line in lines)


def test_fill_survives_a_client_that_blows_up():
    """코멘트 한 칸 때문에 그날 영상이 통째로 없어지면 안 된다."""

    class Broken:
        class messages:
            @staticmethod
            def create(**_):
                raise RuntimeError("연결이 끊겼다")

    lines = []
    assert operator_note.fill(SCRIPT, client=Broken(), log=lines.append) == SCRIPT
    assert any("받지 못했다" in line for line in lines)


def test_fill_does_not_overwrite_what_a_person_wrote():
    mine = "그때 나는 데이터를 안 보고 움직였다."
    already = operator_note.insert(SCRIPT, mine)
    client = FakeClient(GOOD)
    assert operator_note.fill(already, client=client, log=lambda *a: None) == already
    assert client.messages.calls == [], "이미 채워져 있는데 모델을 불렀다"


def test_the_writing_loop_still_has_to_leave_the_section_empty():
    """이 모듈이 생겼다고 검증기가 느슨해지지 않았는지 본다.

    두 단계가 섞이면 작성 모델이 제 대본에 사람 목소리를 넣고도 통과하게 된다.
    그걸 막는 것이 이 프로젝트의 뼈대다.
    """
    filled = operator_note.insert(SCRIPT, GOOD)
    violations = validator.validate(filled, SCRIPT)
    assert any("비워야 한다" in str(v) for v in violations)
