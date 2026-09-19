"""업로드 — 네트워크를 타지 않는다.

유튜브에 닿기 **전까지**를 본다. 여기 있는 경우들은 전부 머니로직에서 한
번씩 실제로 난 것이고, 한 번 나간 영상은 되돌리기 번거롭다.
"""

import json

import pytest

import upload


# --- 자격 증명 -----------------------------------------------------------

# `MV` 는 MoneyLogic 에서 온 글자지만 그 채널은 없다 — 이름을 바꾼 것이지
# 지운 것이 아니라서 같은 채널이 지금 「귀트는 일본어」다. 접두사를 안 바꾼
# 이유는 GitHub 시크릿의 값을 다시 읽을 수 없기 때문이다(upload.py 참고).
FULL = {"MV_CLIENT_ID": "id", "MV_CLIENT_SECRET": "secret",
        "MV_REFRESH_TOKEN": "token"}


def test_complete_credentials_are_read():
    assert upload.credentials(FULL)["CLIENT_ID"] == "id"


def test_missing_credentials_are_named_not_guessed():
    with pytest.raises(SystemExit) as stopped:
        upload.credentials({"MV_CLIENT_ID": "id"})
    message = str(stopped.value)
    assert "MV_CLIENT_SECRET" in message and "MV_REFRESH_TOKEN" in message


def test_blank_credentials_count_as_missing():
    """워크플로는 없는 시크릿을 빈 문자열로 넘긴다."""
    with pytest.raises(SystemExit):
        upload.credentials({**FULL, "MV_REFRESH_TOKEN": "   "})


def test_there_is_no_fallback_to_the_shared_credentials():
    """공용 YT_* 로 넘어가면 이 채널 시크릿을 깜빡한 날 남의 채널로 올라간다."""
    shared = {"YT_CLIENT_ID": "id", "YT_CLIENT_SECRET": "secret",
              "YT_REFRESH_TOKEN": "token"}
    with pytest.raises(SystemExit) as stopped:
        upload.credentials(shared)
    assert "MV_CLIENT_ID" in str(stopped.value)


def test_the_retired_channels_credentials_are_not_accepted():
    """머니로직 말고 **다른** 접은 채널 값으로는 올라가지 않는다.

    머니로직의 MV_* 는 이 채널 것이 맞다(이름만 바꿨다). 하지만 채널푸드의
    WEIRD_* 는 정말 남의 것이고, 저장소 설정에 아직 남아 있을 수 있다.
    """
    other = {"WEIRD_CLIENT_ID": "id", "WEIRD_CLIENT_SECRET": "secret",
             "WEIRD_REFRESH_TOKEN": "token"}
    with pytest.raises(SystemExit):
        upload.credentials(other)


def test_the_error_never_prints_a_credential_value():
    """오류 메시지는 로그에 남는다. 이름만 말하고 값은 말하지 않는다."""
    with pytest.raises(SystemExit) as stopped:
        upload.credentials({"MV_CLIENT_ID": "sk-비밀값"})
    assert "sk-비밀값" not in str(stopped.value)


# --- 두 번 올리지 않기 ----------------------------------------------------

def test_an_already_uploaded_folder_stops():
    """머니로직은 같은 제목이 여러 번 올라갔다 — 날짜로 막아 뒀던 탓이다."""
    with pytest.raises(SystemExit) as stopped:
        upload.assert_not_uploaded({"youtube_video_id": "abc123"}, again=False)
    assert "abc123" in str(stopped.value)


def test_a_fresh_folder_passes():
    assert upload.assert_not_uploaded({}, again=False) is None


def test_a_blank_video_id_is_treated_as_not_uploaded():
    assert upload.assert_not_uploaded({"youtube_video_id": "  "}, again=False) is None


def test_again_allows_a_deliberate_second_upload():
    assert upload.assert_not_uploaded({"youtube_video_id": "abc"}, again=True) is None


# --- 올리기 직전 재검사 ---------------------------------------------------

def sound_meta(**overrides):
    base = {
        "title": "잠들기 전 일본어 듣기 32분 | 자면서 듣는 일본어 회화 150문장",
        "description": "잠들기 전에 틀어 두는 32분 일본어 듣기입니다.",
        "phrase_ids": [f"J{n:03d}" for n in range(1, 151)],
        "duration_seconds": 1932.0,
        "target_minutes": 40,
    }
    return {**base, **overrides}


def test_a_sound_build_passes_the_second_check():
    assert upload.verify_before_upload(sound_meta()) is None


def test_a_hand_edited_broken_title_is_caught_at_upload_time():
    """build 와 upload 는 다른 실행이다. 그 사이에 손을 댔을 수 있다."""
    with pytest.raises(SystemExit) as stopped:
        upload.verify_before_upload(sound_meta(title="일본어 nan분 듣기"))
    assert "nan" in str(stopped.value)


def test_an_empty_build_is_caught_at_upload_time():
    with pytest.raises(SystemExit):
        upload.verify_before_upload(sound_meta(phrase_ids=[]))


def test_a_length_that_no_longer_matches_its_label_is_caught():
    with pytest.raises(SystemExit):
        upload.verify_before_upload(
            sound_meta(duration_seconds=600.0, target_minutes=40))


# --- 올릴 본문 -----------------------------------------------------------

def test_the_language_is_korean_because_the_viewer_is():
    """일본어를 가르치지만 설명과 뜻이 한국어다. 한국어 시청자에게 가야 한다."""
    body = upload.video_body(sound_meta())
    assert body["snippet"]["defaultLanguage"] == "ko"
    assert body["snippet"]["defaultAudioLanguage"] == "ko"


def test_privacy_defaults_to_what_the_build_decided():
    """build.py 가 private 으로 적는다. 여기서 조용히 뒤집지 않는다."""
    body = upload.video_body(sound_meta(privacyStatus="private"))
    assert body["status"]["privacyStatus"] == "private"


def test_a_metadata_without_privacy_still_does_not_go_public():
    """칸이 빠졌다고 공개로 나가면 안 된다. 모르면 가장 조용한 쪽이다."""
    body = upload.video_body(sound_meta())
    assert body["status"]["privacyStatus"] == "private"


def test_an_explicit_flag_overrides_the_metadata():
    body = upload.video_body(sound_meta(privacyStatus="private"), "public")
    assert body["status"]["privacyStatus"] == "public"


def test_videos_are_never_marked_made_for_kids():
    """아동용으로 표시되면 댓글과 여러 기능이 꺼진다."""
    assert upload.video_body(sound_meta())["status"]["madeForKids"] is False


# --- 빌드 폴더 -----------------------------------------------------------

def test_a_folder_without_metadata_stops(tmp_path):
    with pytest.raises(SystemExit) as stopped:
        upload.load_build(tmp_path)
    assert "metadata.json" in str(stopped.value)


def test_a_folder_without_a_video_stops(tmp_path):
    (tmp_path / "metadata.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as stopped:
        upload.load_build(tmp_path)
    assert "video.mp4" in str(stopped.value)


def test_a_complete_folder_loads(tmp_path):
    (tmp_path / "metadata.json").write_text(
        json.dumps(sound_meta(), ensure_ascii=False), encoding="utf-8")
    (tmp_path / "video.mp4").write_bytes(b"\x00")
    _, meta, video = upload.load_build(tmp_path)
    assert meta["target_minutes"] == 40 and video.name == "video.mp4"
