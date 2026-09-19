"""문장 은행 검사 — 네트워크를 타지 않는다.

여기 있는 경우는 전부 초안에서 실제로 났던 것이다. 지어낸 시나리오가 아니라
한 번씩 저지른 실수라서, 회귀 검사로서 값이 있다.
"""

import build_bank


def entry(**overrides):
    """온전한 문장 하나. 검사하려는 칸만 덮어쓴다."""
    base = {
        "ja": "おはようございます。", "yomi": "오하요오 고자이마스",
        "ko": "좋은 아침입니다",
        "ex_ja": "部長、おはようございます。",
        "ex_yomi": "부초오, 오하요오 고자이마스",
        "ex_ko": "부장님, 좋은 아침입니다.",
        "topic": "인사·기본",
    }
    return {**base, **overrides}


def problems(**overrides):
    return build_bank.check_entry("조각.json", 0, entry(**overrides))


# --- 온전한 문장 ---------------------------------------------------------

def test_a_complete_entry_passes():
    assert problems() == []


def test_roman_letters_in_japanese_are_allowed():
    """Wi-Fi·M 사이즈는 일본어 문장에서도 로마자로 쓴다."""
    assert problems(ja="Wi-Fiのパスワードを教えてください。",
                    ex_ja="すみません、Wi-Fiは使えますか。") == []


# --- 빈 칸 ---------------------------------------------------------------

def test_a_missing_field_is_named():
    found = build_bank.check_entry("조각.json", 0, {"ja": "はい。"})
    assert any("yomi 가 비었다" in problem for problem in found)


def test_a_whitespace_field_counts_as_empty():
    """공백만 든 칸은 카드에서 빈 줄로 나온다. 있는 것으로 세면 안 된다."""
    assert any("ko 가 비었다" in problem for problem in problems(ko="   "))


def test_an_empty_field_stops_before_content_checks():
    """비어 있으면 '한글이 없다'까지 같이 쏟아져 진짜 문제가 묻힌다."""
    found = problems(yomi="")
    assert len(found) == 1


# --- 칸이 뒤바뀐 경우 -----------------------------------------------------

def test_korean_in_the_japanese_field_is_caught():
    """07-관광 초안에서 났다. TTS 가 일본어 음성으로 한글을 읽으려 한다."""
    assert any("한글이 섞였다" in problem
               for problem in problems(ja="천천히 보고 싶습니다。"))


def test_a_japanese_field_without_japanese_is_caught():
    assert any("일본어 글자가 없다" in problem for problem in problems(ja="OK"))


def test_a_stray_kana_in_the_reading_is_caught():
    """05-교통 초안에 'ん' 하나가 읽기 칸에 남아 있었다. 카드에 그대로 찍힌다."""
    assert any("일본어 글자가 섞였다" in problem
               for problem in problems(ex_yomi="운텐슈사ん, 코노 주우쇼마데"))


def test_kanji_in_the_meaning_field_is_caught():
    """뜻 칸은 한국어다. 한자가 남으면 번역을 빠뜨린 것이다."""
    assert any("일본어 글자가 섞였다" in problem for problem in problems(ko="좋은 朝입니다"))


def test_a_reading_with_no_hangul_is_caught():
    assert any("한글이 없다" in problem for problem in problems(yomi="ohayou"))


def test_every_broken_field_is_reported_not_just_the_first():
    """하나만 알려주면 고치고 다시 돌리기를 칸 수만큼 해야 한다."""
    found = problems(ja="천천히", yomi="ohayou")
    assert len(found) >= 3


# --- 중복 ---------------------------------------------------------------

def test_a_repeated_sentence_is_dropped_once():
    kept, dropped = build_bank.drop_duplicates(
        [entry(), entry(topic="호텔·숙박"), entry(ja="こんにちは。")])
    assert [item["ja"] for item in kept] == ["おはようございます。", "こんにちは。"]
    assert dropped == ["おはようございます。"]


def test_the_first_occurrence_is_the_one_kept():
    """주제 순서가 곧 영상 순서라, 먼저 나온 자리를 지켜야 한다."""
    kept, _ = build_bank.drop_duplicates(
        [entry(topic="인사·기본"), entry(topic="호텔·숙박")])
    assert kept[0]["topic"] == "인사·기본"


def test_dropped_sentences_are_reported_not_silent():
    """조용히 줄면 150문장을 넣었는데 영상이 짧아진 이유를 못 찾는다."""
    _, dropped = build_bank.drop_duplicates([entry(), entry()])
    assert dropped == ["おはようございます。"]


# --- 번호 ---------------------------------------------------------------

def test_ids_start_at_one_and_are_zero_padded():
    """used.json 이 이 값으로 '쓴 문장'을 기억한다. 폭이 흔들리면 못 찾는다."""
    numbered = build_bank.assign_ids([entry(), entry(ja="こんにちは。")])
    assert [item["id"] for item in numbered] == ["J001", "J002"]


def test_the_id_comes_first_in_the_entry():
    """카드와 로그에서 사람이 먼저 보는 값이다."""
    numbered = build_bank.assign_ids([entry()])
    assert next(iter(numbered[0])) == "id"


def test_assigning_ids_keeps_every_field():
    numbered = build_bank.assign_ids([entry()])
    assert set(numbered[0]) == set(build_bank.FIELDS) | {"id"}


# --- 실제 은행 -----------------------------------------------------------

def test_the_real_bank_passes_its_own_checks():
    """조각 파일을 손으로 고친 뒤 이 검사를 건너뛰지 않게 한다."""
    entries = build_bank.load_parts()
    assert len(entries) > 250


def test_the_real_bank_has_no_duplicate_ids_after_building():
    entries, _ = build_bank.drop_duplicates(build_bank.load_parts())
    numbered = build_bank.assign_ids(entries)
    assert len({item["id"] for item in numbered}) == len(numbered)
