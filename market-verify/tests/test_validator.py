import pytest

from src.validator import REQUIRED_HEADERS, STRUCTURAL_NUMBERS, validate
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


def test_structural_allowlist_is_only_the_cut_numbers():
    """허용셋이 넓어지면 환각 탐지가 헐거워진다. 넓힐 때는 이 테스트를 먼저 볼 것."""
    assert STRUCTURAL_NUMBERS == {"1", "2", "3"}


def test_block_does_not_need_an_allowlist_line():
    assert "허용 숫자" not in BLOCK


def test_cut_numbering_is_allowed_without_being_in_the_block():
    assert "2" not in _block_numbers()
    assert validate(SCRIPT, BLOCK) == []


def test_duration_number_is_no_longer_allowed():
    broken = SCRIPT.replace(
        "## 숏폼 컷 3개\n", "## 숏폼 컷 3개\n각 컷은 60초 이내로 자른다.\n"
    )
    assert "데이터 블록에 없는 숫자: 60" in validate(broken, BLOCK)


def test_section_number_beyond_three_is_not_allowed_in_body():
    broken = SCRIPT.replace("표본은 12건입니다.", "표본은 12건이고 조건은 7가지입니다.")
    assert "데이터 블록에 없는 숫자: 7" in validate(broken, BLOCK)


def _block_numbers():
    from src.validator import _extract_numbers

    return _extract_numbers(BLOCK)
