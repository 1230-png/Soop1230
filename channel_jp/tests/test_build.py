"""발행 차단 게이트 — 네트워크도 ffmpeg 도 타지 않는다.

머니로직이 제목에 `nan%` 가 박힌 영상을 여드레 동안 공개로 올린 뒤에 세운
검사다. 여기 있는 경우들이 그때 통과해 버린 것들이다.
"""

import pytest

import build


def metadata(**overrides):
    """발행해도 되는 metadata 한 벌. 검사하려는 칸만 덮어쓴다."""
    base = {
        "title": "잠들기 전 일본어 듣기 40분 | 자면서 듣는 일본어 회화 150문장",
        "description": "잠들기 전에 틀어 두는 40분 일본어 듣기입니다.",
        "phrase_ids": ["J001", "J002"],
        "duration_seconds": 2400.0,
    }
    return {**base, **overrides}


def refusal(meta, minutes=40, target=40):
    """verify_publishable 이 멈추면 그 이유. 통과하면 None."""
    try:
        build.verify_publishable(meta, minutes, target)
    except SystemExit as stop:
        return str(stop)
    return None


# --- 통과해야 하는 것 -----------------------------------------------------

def test_a_sound_video_is_published():
    assert refusal(metadata()) is None


def test_a_length_within_tolerance_passes():
    """30%까지는 봐 준다. 그보다 좁히면 문장 길이가 조금만 흔들려도 멈춘다."""
    assert refusal(metadata(), minutes=48, target=40) is None


def test_no_target_means_no_length_check():
    """--limit 을 준 시험 실행이 여기로 온다. 짧은 것이 정상이다."""
    assert refusal(metadata(duration_seconds=120.0), minutes=2, target=None) is None


# --- 깨진 값 -------------------------------------------------------------

def test_nan_in_the_title_stops_publishing():
    """머니로직에서 실제로 나간 것. `float('nan') >= 0` 이 False 라 생겼다."""
    stopped = refusal(metadata(title="일본어 nan% 오늘의 표현"))
    assert stopped and "nan" in stopped


def test_none_in_the_description_stops_publishing():
    """파이썬이 값을 못 채우면 문자열에 None 을 그대로 남긴다."""
    stopped = refusal(metadata(description="문장 None개를 모았습니다"))
    assert stopped and "None" in stopped


def test_an_unfilled_placeholder_stops_publishing():
    """format() 을 빠뜨리면 중괄호가 그대로 제목에 남는다."""
    stopped = refusal(metadata(title="일본어 듣기 {minutes}분"))
    assert stopped and "{minutes}" in stopped


def test_nan_inside_a_word_is_not_a_false_alarm():
    """'nan' 은 흔한 글자 배열이다. 단어 경계로 봐야 멀쩡한 제목을 안 막는다."""
    assert refusal(metadata(title="난바(nanba) 역 근처 일본어")) is None


# --- 빈 영상 -------------------------------------------------------------

def test_a_video_with_no_phrases_stops_publishing():
    """합성이 전부 실패해도 인트로·아웃트로만으로 파일은 만들어진다."""
    stopped = refusal(metadata(phrase_ids=[]))
    assert stopped and "문장이 하나도 없다" in stopped


def test_a_video_shorter_than_a_minute_stops_publishing():
    stopped = refusal(metadata(duration_seconds=30.0), minutes=1, target=None)
    assert stopped and "30초" in stopped


# --- 이름표와 실제가 다른 것 ----------------------------------------------

def test_a_video_far_under_its_label_stops_publishing():
    """제목이 40분이라고 적었는데 12분이면 시청자에게 거짓말이다."""
    stopped = refusal(metadata(), minutes=12, target=40)
    assert stopped and "거짓말" in stopped


def test_a_video_far_over_its_label_also_stops_publishing():
    """길어지는 쪽도 막는다. 이름표가 맞지 않는 것은 마찬가지다."""
    assert refusal(metadata(), minutes=90, target=40) is not None


def test_every_problem_is_reported_at_once():
    """하나씩 알려주면 고치고 다시 빌드하기를 문제 수만큼 해야 한다."""
    stopped = refusal(metadata(title="nan 분", phrase_ids=[]), minutes=2, target=40)
    assert stopped.count("\n  - ") >= 2


# --- 합성 전 문장 검사 ----------------------------------------------------

def sound_phrase(**overrides):
    base = {
        "id": "J001", "ja": "おはようございます。", "yomi": "오하요오 고자이마스",
        "ko": "좋은 아침입니다", "ex_ja": "部長、おはようございます。",
        "ex_yomi": "부초오, 오하요오 고자이마스",
        "ex_ko": "부장님, 좋은 아침입니다.", "topic": "인사·기본",
    }
    return {**base, **overrides}


def test_sound_phrases_start_synthesis():
    assert build.verify_phrases([sound_phrase()]) is None


def test_a_broken_phrase_stops_before_any_synthesis():
    """수면 팩 한 편이 edge-tts 를 450번 부른다. 그 앞에서 막아야 한다."""
    with pytest.raises(SystemExit) as stopped:
        build.verify_phrases([sound_phrase(), sound_phrase(ja="천천히 보고 싶어요")])
    assert "합성을 시작하지 않는다" in str(stopped.value)


# --- 문장 고르기 ---------------------------------------------------------

def test_unused_phrases_come_first():
    pool = [sound_phrase(id="J001"), sound_phrase(id="J002"),
            sound_phrase(id="J003")]
    state = {"packs": {"p": {"J001": "2026-09-01"}}}
    picked = build.pick_phrases(pool, "p", 2, state)
    assert [item["id"] for item in picked] == ["J002", "J003"]


def test_when_the_pool_runs_short_the_oldest_are_reused_first():
    """되돌려 쓰기가 고르게 퍼져야 같은 몇 개만 계속 나오지 않는다."""
    pool = [sound_phrase(id="J001"), sound_phrase(id="J002")]
    state = {"packs": {"p": {"J001": "2026-09-05", "J002": "2026-09-01"}}}
    picked = build.pick_phrases(pool, "p", 1, state)
    assert picked[0]["id"] == "J002"


def test_recycling_is_counted_per_pack_not_per_channel():
    """쉐도잉에 나온 문장은 수면 팩에서는 아직 새 것이다."""
    pool = [sound_phrase(id="J001")]
    state = {"packs": {"shadowing_drill": {"J001": "2026-09-01"}}}
    picked = build.pick_phrases(pool, "sleep_japanese", 1, state)
    assert picked[0]["id"] == "J001"


def test_a_topic_filter_only_draws_from_those_topics():
    pool = [sound_phrase(id="J001", topic="인사·기본"),
            sound_phrase(id="J002", topic="교통·길찾기")]
    picked = build.pick_phrases(pool, "p", 2, {}, include=["교통·길찾기"])
    assert [item["id"] for item in picked] == ["J002"]


def test_a_topic_with_no_phrases_stops_rather_than_building_an_empty_video():
    with pytest.raises(SystemExit):
        build.pick_phrases([sound_phrase()], "p", 1, {}, include=["없는주제"])


# --- 타임스탬프 ----------------------------------------------------------

@pytest.mark.parametrize("seconds,text", [
    (0, "0:00"), (9, "0:09"), (65, "1:05"), (600, "10:00"),
    (3600, "1:00:00"), (3725, "1:02:05"),
])
def test_chapter_timestamps_match_what_youtube_parses(seconds, text):
    """설명란의 챕터는 이 표기여야 유튜브가 알아본다."""
    assert build.fmt_timestamp(seconds) == text
