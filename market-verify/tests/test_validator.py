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
    assert any(v.startswith("데이터 블록에 없는 숫자: 73.9") for v in violations)


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
    assert any(
        v.startswith("데이터 블록에 없는 숫자: 4242") for v in validate(broken, BLOCK)
    )


def test_multiple_violations_are_all_reported():
    broken = SCRIPT.replace("## 7. 엔딩", "## 삭제됨")
    broken = broken.replace("상승비율은 58.3입니다", "상승비율은 73.9로 급등했습니다")
    violations = validate(broken, BLOCK)
    assert "필수 헤더 누락: ## 7. 엔딩" in violations
    assert "금지어 사용: 급등" in violations
    assert any(v.startswith("데이터 블록에 없는 숫자: 73.9") for v in violations)


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
    assert any(
        v.startswith("데이터 블록에 없는 숫자: 60") for v in validate(broken, BLOCK)
    )


def test_section_number_beyond_three_is_not_allowed_in_body():
    broken = SCRIPT.replace("표본은 12건입니다.", "표본은 12건이고 조건은 7가지입니다.")
    assert any(
        v.startswith("데이터 블록에 없는 숫자: 7") for v in validate(broken, BLOCK)
    )


def _block_numbers():
    from src.validator import _extract_numbers

    return _extract_numbers(BLOCK)


def test_horizontal_rule_under_operator_header_is_not_a_comment():
    """모델이 섹션 구분선으로 --- 를 넣는다. 사람이 쓴 코멘트가 아니므로 통과시킨다."""
    for rule in ["---", "***", "___"]:
        ok = SCRIPT.replace(
            "## 6. [운영자 코멘트]\n\n", f"## 6. [운영자 코멘트]\n\n{rule}\n\n"
        )
        assert validate(ok, BLOCK) == [], f"{rule} 를 코멘트로 오인했다"


def test_real_comment_next_to_a_rule_is_still_caught():
    broken = SCRIPT.replace(
        "## 6. [운영자 코멘트]\n\n",
        "## 6. [운영자 코멘트]\n\n---\n저는 이때 비중을 줄였습니다.\n\n",
    )
    assert any("운영자 코멘트] 섹션은 비워야 한다" in v for v in validate(broken, BLOCK))


def test_year_from_a_block_date_is_allowed():
    """블록에 1990-01-02 가 있으면 대본이 "1990년"이라 부르는 것은 환각이 아니다."""
    ok = SCRIPT.replace("표본은 12건입니다.", "표본은 12건이고 1990년부터 봤습니다.")
    assert validate(ok, BLOCK) == []


def test_year_not_in_the_block_is_still_caught():
    broken = SCRIPT.replace("표본은 12건입니다.", "표본은 12건이고 1987년도 있었습니다.")
    assert any(
        v.startswith("데이터 블록에 없는 숫자: 1987") for v in validate(broken, BLOCK)
    )


def test_month_alone_is_not_allowed_by_the_year_rule():
    """연도만 열어 준다. 월을 따로 떼면 날짜를 그대로 인용하라는 규칙이 무너진다."""
    broken = SCRIPT.replace("표본은 12건입니다.", "표본은 12건이고 8월이 특히 그랬습니다.")
    assert any(
        v.startswith("데이터 블록에 없는 숫자: 8") for v in validate(broken, BLOCK)
    )


def test_violation_names_the_sentence_to_fix():
    """문장을 같이 줘야 모델이 어디를 고칠지 안다."""
    broken = SCRIPT.replace(
        "표본은 12건입니다.", "표본은 12건이고 36년간의 기록입니다."
    )
    hit = [v for v in validate(broken, BLOCK) if v.startswith("데이터 블록에 없는 숫자: 36")]
    assert hit, "36 을 잡지 못했다"
    assert "해당 문장:" in hit[0]
    assert "36년간의 기록입니다" in hit[0]


def test_html_comment_under_operator_header_is_not_a_comment():
    """저장할 때 넣는 작성 안내는 시청자에게 보이지 않는다. 위반이 아니다."""
    ok = SCRIPT.replace(
        "## 6. [운영자 코멘트]\n\n",
        "## 6. [운영자 코멘트]\n<!-- 여기에 직접 쓰세요 -->\n\n",
    )
    assert validate(ok, BLOCK) == []


def test_real_text_beside_an_html_comment_is_still_caught():
    broken = SCRIPT.replace(
        "## 6. [운영자 코멘트]\n\n",
        "## 6. [운영자 코멘트]\n<!-- 안내 -->\n저는 이때 비중을 줄였습니다.\n\n",
    )
    assert any("운영자 코멘트] 섹션은 비워야 한다" in v for v in validate(broken, BLOCK))
