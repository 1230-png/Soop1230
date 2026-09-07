import pytest

from src import script_parse as sp
from tests.fixtures import SCRIPT

FILLED = SCRIPT.replace(
    "## 6. [운영자 코멘트]\n\n",
    "## 6. [운영자 코멘트]\n저는 그때 데이터를 안 보고 움직였습니다.\n\n",
)


def test_titles_returns_three():
    assert len(sp.titles(SCRIPT)) == 3
    assert sp.titles(SCRIPT)[0].startswith("S&P 500")


def test_description_keeps_the_fixed_last_line():
    assert sp.description(SCRIPT).splitlines()[-1].endswith("투자 권유나 조언이 아닙니다.")


def test_shorts_cuts_are_extracted_but_not_narrated():
    cuts = sp.shorts_cuts(SCRIPT)
    assert len(cuts) == 3
    assert all(cut not in sp.narration_text(SCRIPT) for cut in cuts)


def test_scenes_cover_every_narrated_section():
    sections = [scene.section for scene in sp.scenes(FILLED)]
    assert sections == [
        "1. 오프닝", "2. 조건 설정", "3. 과거 사례",
        "4. 결과", "5. 데이터의 한계", "6. [운영자 코멘트]", "7. 엔딩",
    ]


def test_empty_operator_section_produces_no_scene():
    sections = [scene.section for scene in sp.scenes(SCRIPT)]
    assert "6. [운영자 코멘트]" not in sections


def test_cue_labels_the_narration_it_follows():
    """대본은 [자료 화면:] 을 설명 대상 문장 뒤에 붙인다."""
    by_section = {scene.section: scene.screen_text for scene in sp.scenes(SCRIPT)}
    assert by_section["1. 오프닝"] == "주간 종가 3주 연속 하락"
    assert by_section["3. 과거 사례"] == "사례 12건"


def test_cue_before_a_paragraph_labels_what_follows():
    """뒤에 붙은 표기가 없는 섹션이면 앞의 표기가 그 문단을 설명한다."""
    script = FILLED.replace(
        "## 7. 엔딩\n",
        '## 7. 엔딩\n[자료 화면: 마무리 / 화면 텍스트 "판단은 각자"]\n',
    )
    scene = [s for s in sp.scenes(script) if s.section == "7. 엔딩"][0]
    assert scene.screen_text == "판단은 각자"


def test_trailing_cue_wins_when_a_section_has_both():
    """앞뒤로 표기가 있으면 방금 읽은 문장에 붙은 뒤쪽을 쓴다."""
    script = FILLED.replace(
        "## 3. 과거 사례\n",
        '## 3. 과거 사례\n[자료 화면: 목록 / 화면 텍스트 "먼저 볼 것"]\n',
    )
    scene = [s for s in sp.scenes(script) if s.section == "3. 과거 사례"][0]
    assert scene.screen_text == "사례 12건"


def test_section_title_is_used_when_no_cue():
    scene = [s for s in sp.scenes(SCRIPT) if s.section == "7. 엔딩"][0]
    assert scene.screen_text == "7. 엔딩"


def test_cue_markers_never_reach_the_narration():
    assert "[자료 화면:" not in sp.narration_text(SCRIPT)
    assert "화면 텍스트" not in sp.narration_text(SCRIPT)


def test_headers_and_list_numbers_are_not_narrated():
    text = sp.narration_text(SCRIPT)
    assert "## " not in text
    assert "제목 3안" not in text
    assert "유튜브 설명란" not in text


def test_operator_guide_comment_is_stripped():
    script = SCRIPT.replace(
        "## 6. [운영자 코멘트]\n\n",
        "## 6. [운영자 코멘트]\n<!-- 여기에 직접 쓰세요 -->\n\n",
    )
    assert "여기에 직접 쓰세요" not in sp.narration_text(script)
    assert "6. [운영자 코멘트]" not in [s.section for s in sp.scenes(script)]


def test_filled_operator_note_is_narrated():
    scene = [s for s in sp.scenes(FILLED) if s.section == "6. [운영자 코멘트]"][0]
    assert "데이터를 안 보고 움직였습니다" in scene.narration


def test_cue_without_screen_text_falls_back_to_the_tail():
    script = FILLED.replace(
        "## 7. 엔딩\n", "## 7. 엔딩\n[자료 화면: 마무리 화면 / 회색 배경]\n"
    )
    scene = [s for s in sp.scenes(script) if s.section == "7. 엔딩"][0]
    assert scene.screen_text == "회색 배경"


def test_scene_equality_is_by_value():
    assert sp.Scene("a", "b", "c") == sp.Scene("a", "b", "c")
    assert sp.Scene("a", "b", "c") != sp.Scene("a", "b", "d")
