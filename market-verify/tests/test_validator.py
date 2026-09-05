import pytest

from src.validator import REQUIRED_HEADERS, validate
from tests.fixtures import BLOCK, SCRIPT


def test_clean_script_passes():
    assert validate(SCRIPT, BLOCK) == []


@pytest.mark.parametrize("header", REQUIRED_HEADERS)
def test_missing_header_is_caught(header):
    broken = SCRIPT.replace(header, "## 삭제된 섹션")
    violations = validate(broken, BLOCK)
    assert any(f"필수 헤더 누락: {header}" == v for v in violations)


@pytest.mark.parametrize(
    "word", ["폭락", "급락", "급등", "떡상", "대폭", "사상 최악", "충격", "지금 당장"]
)
def test_banned_word_is_caught(word):
    broken = SCRIPT.replace("단순 비교는 어렵습니다.", f"{word}이라는 표현을 넣었습니다.")
    violations = validate(broken, BLOCK)
    assert any(v == f"금지어 사용: {word}" for v in violations)


def test_missing_judgement_phrase_is_caught():
    broken = SCRIPT.replace("판단은 각자", "각자 알아서")
    assert any("필수 문구 누락: 판단은 각자" == v for v in validate(broken, BLOCK))


def test_missing_disclaimer_is_caught():
    broken = SCRIPT.replace("투자 권유나 조언이 아닙니다", "참고용입니다")
    violations = validate(broken, BLOCK)
    assert any("필수 문구 누락: 투자 권유나 조언이 아닙니다" == v for v in violations)


def test_too_few_visual_cues_is_caught():
    broken = SCRIPT.replace("[자료 화면: 표본 한계 / 화면 텍스트 \"표본 12건\"]", "")
    violations = validate(broken, BLOCK)
    assert any("자료 화면" in v and "4개" in v for v in violations)


def test_exactly_five_visual_cues_passes():
    assert SCRIPT.count("[자료 화면:") == 5
    assert validate(SCRIPT, BLOCK) == []


def test_filled_operator_comment_is_caught():
    broken = SCRIPT.replace(
        "## 6. [운영자 코멘트]\n\n",
        "## 6. [운영자 코멘트]\n저는 이 구간에서 비중을 줄였습니다.\n\n",
    )
    violations = validate(broken, BLOCK)
    assert any("운영자 코멘트] 섹션은 비워야 한다" in v for v in violations)


def test_empty_operator_comment_with_whitespace_passes():
    ok = SCRIPT.replace("## 6. [운영자 코멘트]\n\n", "## 6. [운영자 코멘트]\n   \n\n")
    assert validate(ok, BLOCK) == []


def test_hallucinated_number_is_caught():
    broken = SCRIPT.replace("상승비율은 58.3입니다", "상승비율은 73.9입니다")
    violations = validate(broken, BLOCK)
    assert "데이터 블록에 없는 숫자: 73.9" in violations


def test_hallucinated_date_is_caught():
    broken = SCRIPT.replace("1994-11-04입니다", "2008-09-15입니다")
    violations = validate(broken, BLOCK)
    assert "데이터 블록에 없는 날짜: 2008-09-15" in violations


def test_decimal_formatting_difference_is_not_a_violation():
    ok = SCRIPT.replace("중앙값은 1.2", "중앙값은 1.20")
    assert validate(ok, BLOCK) == []


def test_list_numbering_does_not_cause_false_positive():
    ok = SCRIPT.replace(
        "## 3. 과거 사례\n",
        "## 3. 과거 사례\n99. 목록 번호는 대본 수치가 아니다\n",
    )
    assert validate(ok, BLOCK) == []


def test_header_numbering_does_not_cause_false_positive():
    ok = SCRIPT.replace("## 7. 엔딩", "## 88. 부록\n\n## 7. 엔딩")
    assert validate(ok, BLOCK) == []


def test_number_inside_list_item_text_is_still_checked():
    broken = SCRIPT.replace(
        "## 3. 과거 사례\n",
        "## 3. 과거 사례\n1. 사례는 사실 4242건이었습니다\n",
    )
    assert "데이터 블록에 없는 숫자: 4242" in validate(broken, BLOCK)


def test_multiple_violations_are_all_reported():
    broken = SCRIPT.replace("## 7. 엔딩", "## 삭제됨")
    broken = broken.replace("상승비율은 58.3입니다", "상승비율은 73.9로 급등했습니다")
    violations = validate(broken, BLOCK)
    assert "필수 헤더 누락: ## 7. 엔딩" in violations
    assert "금지어 사용: 급등" in violations
    assert "데이터 블록에 없는 숫자: 73.9" in violations
