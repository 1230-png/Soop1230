"""채널 설명·키워드 — 네트워크를 타지 않는다.

여기서 지키는 것은 하나다: **사람이 적어 둔 값을 코드가 조용히 덮어쓰지
않는다.** 되돌리려면 그 사람이 무엇을 잃었는지부터 알아내야 하는데, 덮어쓴
쪽은 그것을 알려 주지 않는다.
"""

import pytest

import channel_settings as settings


def branding(**channel):
    return {"channel": channel}


# --- 한도 ----------------------------------------------------------------

def test_the_real_values_fit_youtube_limits():
    """넘긴 채로 보내면 요청 전체가 거절돼 멀쩡한 칸까지 같이 안 들어간다."""
    settings.check_limits(
        settings.format_keywords(settings.KEYWORDS), settings.DESCRIPTION)


def test_keywords_over_the_limit_stop_before_the_network():
    with pytest.raises(settings.SettingsError) as stopped:
        settings.check_limits("가" * (settings.KEYWORDS_MAX + 1), "설명")
    assert "키워드" in str(stopped.value)


def test_a_description_over_the_limit_stops():
    with pytest.raises(settings.SettingsError) as stopped:
        settings.check_limits("키워드", "가" * (settings.DESCRIPTION_MAX + 1))
    assert "설명" in str(stopped.value)


def test_only_multiword_terms_are_quoted():
    """전부 묶으면 500자 한도에서 말마다 두 글자씩 그냥 버린다."""
    got = settings.format_keywords(["일본어듣기", "learn japanese"])
    assert got == '일본어듣기 "learn japanese"'


# --- 비어 있는 칸만 채운다 -------------------------------------------------

def test_empty_fields_are_filled():
    _, changes = settings.plan_changes(branding(), force=False)
    assert len(changes) == 3


def test_what_the_owner_already_wrote_is_left_alone():
    """이 파일이 있는 이유다. 덮어쓰면 그 사람은 무엇을 잃었는지도 모른다."""
    before = branding(keywords="손으로 적은 것", description="손으로 적은 설명",
                      defaultLanguage="ko")
    after, changes = settings.plan_changes(before, force=False)
    assert changes == []
    assert after["channel"]["description"] == "손으로 적은 설명"


def test_whitespace_only_counts_as_empty():
    """유튜브는 안 채운 칸을 빈 문자열로 준다. 공백만 있는 것도 마찬가지다."""
    _, changes = settings.plan_changes(branding(description="   "), force=False)
    assert any("설명" in c for c in changes)


def test_force_overwrites_but_only_when_asked():
    before = branding(keywords="옛날 것", description="옛날 설명",
                      defaultLanguage="ko")
    after, changes = settings.plan_changes(before, force=True)
    assert after["channel"]["description"] == settings.DESCRIPTION
    assert after["channel"]["keywords"] != "옛날 것"
    # 기본 언어는 이미 차 있으므로 --force 여도 건드리지 않는다. 덮어쓰기는
    # 키워드와 설명에만 걸린다.
    assert len(changes) == 2


def test_planning_does_not_mutate_what_it_was_given():
    """부르는 쪽이 원본을 다시 볼 수 있어야 무엇이 바뀌는지 찍을 수 있다."""
    before = branding(description="옛날 설명")
    settings.plan_changes(before, force=True)
    assert before["channel"]["description"] == "옛날 설명"


# --- 남의 채널 -----------------------------------------------------------

def channel_item(channel_id, title="귀트는 일본어"):
    return {"id": channel_id, "snippet": {"title": title}}


def test_another_channel_is_refused():
    """남의 채널 설명을 갈아 끼우면 되돌리기가 특히 번거롭다."""
    with pytest.raises(settings.SettingsError) as stopped:
        settings.assert_right_channel(
            channel_item("UC-남의채널"), {"MV_CHANNEL_ID": "UC-우리채널"})
    assert "다르다" in str(stopped.value)


def test_without_the_channel_id_it_prints_the_real_one_and_stops():
    """upload.py 와 같은 규칙 — 짐작해서 고치지 않는다."""
    with pytest.raises(settings.SettingsError) as stopped:
        settings.assert_right_channel(channel_item("UC-진짜채널"), {})
    message = str(stopped.value)
    assert "UC-진짜채널" in message and "MV_CHANNEL_ID" in message


def test_the_right_channel_passes():
    settings.assert_right_channel(
        channel_item("UC-우리채널"), {"MV_CHANNEL_ID": " UC-우리채널 "})


# --- 자격 증명 -----------------------------------------------------------

def test_missing_credentials_do_not_fall_back_to_the_shared_ones():
    """대체 경로를 두지 않는다 — 남의 자격 증명으로 고치느니 멈춘다(CLAUDE.md)."""
    with pytest.raises(settings.SettingsError) as stopped:
        settings.youtube_client({"YT_CLIENT_ID": "남의 것"})
    assert "MV_CLIENT_ID" in str(stopped.value)


# --- 내용 ----------------------------------------------------------------

def test_the_description_names_the_upload_days():
    """채널을 처음 본 사람이 다음 편이 언제인지 알 수 있어야 구독한다."""
    for day in ("화요일", "목요일", "금요일"):
        assert day in settings.DESCRIPTION


def test_keywords_are_not_japanese():
    """시청자가 한국어 화자다. 일본어 검색어는 한국어를 배우는 일본인을
    끌어오는데, 이 채널의 뜻풀이가 전부 한국어라 그들에게는 쓸모가 없다.
    """
    import re
    kana = re.compile(r"[぀-ゟ゠-ヿ]")
    assert not [k for k in settings.KEYWORDS if kana.search(k)]
