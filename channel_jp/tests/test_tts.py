"""음성 합성 — 네트워크를 타지 않는다.

ElevenLabs 는 글자 수로 돈을 받고 키가 있어야 한다. 그래서 여기서 확인하는
것은 **호출 직전까지**다: 요청이 제대로 서는지, 키가 없을 때 조용히 다른
엔진으로 넘어가지 않는지, 같은 문장에 값을 두 번 내지 않는지.
"""

import json

import pytest

from lib import tts


# --- 속도 표기 -----------------------------------------------------------

@pytest.mark.parametrize("rate,tempo", [
    ("+0%", 1.0), ("-20%", 0.8), ("-15%", 0.85), ("+25%", 1.25),
])
def test_edge_style_rates_become_atempo_values(rate, tempo):
    """packs.yaml 이 엔진마다 다른 말을 하지 않게, 표기를 하나로 둔다."""
    assert tts.tempo_for(rate) == pytest.approx(tempo)


@pytest.mark.parametrize("rate", ["", "느리게", "20", "-20"])
def test_an_unreadable_rate_stops_rather_than_guessing(rate):
    with pytest.raises(tts.TTSError):
        tts.tempo_for(rate)


@pytest.mark.parametrize("rate", ["-60%", "+150%"])
def test_a_rate_outside_the_atempo_range_stops(rate):
    """범위를 벗어나면 ffmpeg 이 조용히 이상한 것을 낸다."""
    with pytest.raises(tts.TTSError) as stopped:
        tts.tempo_for(rate)
    assert "atempo" in str(stopped.value)


# --- 키 ------------------------------------------------------------------

def test_a_missing_key_stops_instead_of_falling_back():
    """되돌아가게 두면 목소리가 통째로 다른 영상이 조용히 올라간다."""
    with pytest.raises(tts.TTSError) as stopped:
        tts.api_key({})
    assert "돌아가지 않는다" in str(stopped.value)


def test_a_blank_key_counts_as_missing():
    """워크플로는 없는 시크릿을 빈 문자열로 넘긴다."""
    with pytest.raises(tts.TTSError):
        tts.api_key({"ELEVENLABS_API_KEY": "   "})


def test_a_present_key_is_returned_stripped():
    assert tts.api_key({"ELEVENLABS_API_KEY": " sk-abc \n"}) == "sk-abc"


# --- 요청 ---------------------------------------------------------------

def test_the_request_carries_the_voice_in_the_url():
    request = tts.build_eleven_request("おはよう", "VOICE123", "sk-x")
    assert request.full_url.endswith("/VOICE123")


def test_the_request_asks_for_the_multilingual_model():
    """일본어와 한국어를 한 목소리로 읽으려면 다국어 모델이어야 한다."""
    request = tts.build_eleven_request("おはよう", "V", "sk-x")
    assert json.loads(request.data)["model_id"] == tts.ELEVEN_MODEL


def test_the_key_travels_in_the_header_not_the_body():
    """본문은 오류 메시지에 실려 나온다. 키가 거기 있으면 로그에 남는다."""
    request = tts.build_eleven_request("おはよう", "V", "sk-secret")
    assert request.get_header("Xi-api-key") == "sk-secret"
    assert "sk-secret" not in request.data.decode("utf-8")


def test_the_text_is_sent_unchanged():
    request = tts.build_eleven_request("駅はどこですか。", "V", "sk-x")
    assert json.loads(request.data)["text"] == "駅はどこですか。"


# --- 캐시 ---------------------------------------------------------------

def test_the_cache_key_separates_the_two_engines():
    """엔진을 바꿔 다시 빌드했는데 예전 목소리가 캐시에서 나오면 안 된다."""
    assert tts._key("あ", "V", "+0%", "edge") != tts._key("あ", "V", "+0%", "elevenlabs")


def test_the_cache_key_separates_speeds():
    assert tts._key("あ", "V", "+0%", "e") != tts._key("あ", "V", "-20%", "e")


def test_the_same_request_lands_on_the_same_cache_key():
    """수면 팩은 한 문장을 두 번 읽는다. 값이 두 번 나가면 안 된다."""
    assert tts._key("あ", "V", "+0%", "e") == tts._key("あ", "V", "+0%", "e")


# --- 엔진 이름 -----------------------------------------------------------

def test_an_unknown_engine_stops():
    with pytest.raises(tts.TTSError) as stopped:
        tts.synthesize("あ", "V", engine="google")
    assert "모르는 엔진" in str(stopped.value)


# --- offline ------------------------------------------------------------

def test_offline_never_reaches_the_network_or_needs_a_key(tmp_path, monkeypatch):
    """키 없이도 파이프라인 전체를 돌려 볼 수 있어야 한다."""
    monkeypatch.setattr(tts, "CACHE_DIR", tmp_path)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    path = tts.synthesize("おはようございます。", "V", offline=True)
    assert path.exists() and path.stat().st_size > 0


def test_offline_silence_is_longer_for_a_longer_sentence(tmp_path, monkeypatch):
    """무음 길이가 글자 수를 따라가야 target_minutes 검사가 뜻을 갖는다."""
    monkeypatch.setattr(tts, "CACHE_DIR", tmp_path)
    short = tts.duration_of(tts.synthesize("はい。", "V", offline=True))
    long = tts.duration_of(
        tts.synthesize("すみません、駅はどこですか。とても急いでいます。",
                       "V", offline=True))
    assert long > short
