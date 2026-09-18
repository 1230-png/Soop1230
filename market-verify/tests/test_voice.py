from pathlib import Path

import pytest

from src import render, voice
from src.script_parse import Scene


def test_silent_speak_matches_the_text_length(tmp_path):
    """무음이라도 길이는 읽는 시간에 맞춘다. 그래야 영상 길이가 현실적이다."""
    short = voice.silent_speak("짧다.", tmp_path / "a.mp3")
    long = voice.silent_speak("이 문장은 앞의 것보다 훨씬 길어서 읽는 데 시간이 더 걸린다." * 3,
                              tmp_path / "b.mp3")
    assert render.audio_duration(long) > render.audio_duration(short)


def test_silent_speak_has_a_floor(tmp_path):
    path = voice.silent_speak("네.", tmp_path / "a.mp3")
    assert render.audio_duration(path) >= 1.4


def test_narrate_makes_one_file_per_scene(tmp_path):
    scenes = [Scene("1. 오프닝", "화면", "첫 문장입니다."),
              Scene("7. 엔딩", "화면", "판단은 각자.")]
    paths = voice.narrate(scenes, tmp_path, speak=voice.silent_speak)
    assert len(paths) == 2
    assert all(p.exists() for p in paths)
    assert [p.name for p in paths] == ["line_001.mp3", "line_002.mp3"]


def test_narrate_passes_each_scene_text_through(tmp_path):
    seen = []

    def fake(text, out_path, voice_name=None):
        seen.append(text)
        return voice.silent_speak(text, out_path)

    scenes = [Scene("s", "화면", "가"), Scene("s", "화면", "나")]
    voice.narrate(scenes, tmp_path, speak=fake)
    assert seen == ["가", "나"]


def test_narrate_creates_the_directory(tmp_path):
    target = tmp_path / "새폴더" / "안쪽"
    voice.narrate([Scene("s", "화면", "가")], target, speak=voice.silent_speak)
    assert target.exists()


def test_default_voice_is_korean():
    assert voice.DEFAULT_VOICE.startswith("ko-KR")


def _boom(*a, **k):
    raise RuntimeError("NoAudioReceived")


def test_edge_failure_falls_back_to_elevenlabs(tmp_path, monkeypatch):
    """깃허브 러너에서는 edge-tts 가 막힌다. 무인 실행이 거기서 멈추면 안 된다."""
    monkeypatch.setattr(voice, "_edge_once", _boom)
    monkeypatch.setattr(voice.time, "sleep", lambda s: None)
    monkeypatch.setenv(voice.ELEVENLABS_KEY_ENV, "키")
    called = {}

    def fake_eleven(text, out_path, voice_id=None):
        called["text"] = text
        Path(out_path).write_bytes(b"mp3")
        return out_path

    monkeypatch.setattr(voice, "elevenlabs_speak", fake_eleven)
    out = voice.edge_tts_speak("한 문장", tmp_path / "a.mp3")
    assert called["text"] == "한 문장"
    assert Path(out).exists()


def test_edge_retries_before_giving_up(tmp_path, monkeypatch):
    """한 번 튕긴 것만으로 넘기지 않는다. 일시적인 실패가 잦다."""
    monkeypatch.setattr(voice.time, "sleep", lambda s: None)
    tries = {"n": 0}

    def flaky(text, out_path, voice_name):
        tries["n"] += 1
        if tries["n"] < 3:
            raise RuntimeError("일시적")
        Path(out_path).write_bytes(b"mp3")
        return out_path

    monkeypatch.setattr(voice, "_edge_once", flaky)
    voice.edge_tts_speak("문장", tmp_path / "a.mp3")
    assert tries["n"] == 3


def test_without_a_key_it_still_tries_the_free_one(tmp_path, monkeypatch):
    """키가 없어도 멈추지 않는다. 구글 번역 음성은 키가 필요 없다."""
    monkeypatch.setattr(voice, "_edge_once", _boom)
    monkeypatch.setattr(voice.time, "sleep", lambda s: None)
    monkeypatch.delenv(voice.ELEVENLABS_KEY_ENV, raising=False)
    called = {}

    def fake_google(text, out_path, lang="ko"):
        called["hit"] = True
        Path(out_path).write_bytes(b"mp3")
        return out_path

    monkeypatch.setattr(voice, "google_speak", fake_google)
    voice.edge_tts_speak("문장", tmp_path / "a.mp3")
    assert called["hit"]


def test_an_empty_voice_id_secret_falls_back_to_the_default(monkeypatch, tmp_path):
    """워크플로는 없는 시크릿을 빈 문자열로 넘긴다. 그걸 값으로 쓰면 주소가 깨진다."""
    monkeypatch.setenv(voice.ELEVENLABS_KEY_ENV, "키")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "")
    seen = {}

    class Response:
        status_code = 200
        content = b"mp3"

    def fake_post(url, **kwargs):
        seen["url"] = url
        return Response()

    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    voice.elevenlabs_speak("문장", tmp_path / "a.mp3")
    assert seen["url"].endswith(voice.ELEVENLABS_DEFAULT_VOICE_ID)
    assert not seen["url"].endswith("/")


def test_google_is_the_last_resort(tmp_path, monkeypatch):
    """일레븐랩스 키가 만료돼 있어도 멈추지 않는다. 뒤에 무료 대안이 있다."""
    monkeypatch.setattr(voice, "_edge_once", _boom)
    monkeypatch.setattr(voice.time, "sleep", lambda s: None)
    monkeypatch.setenv(voice.ELEVENLABS_KEY_ENV, "만료된키")
    monkeypatch.setattr(voice, "elevenlabs_speak", _boom)
    called = {}

    def fake_google(text, out_path, lang="ko"):
        called["text"] = text
        Path(out_path).write_bytes(b"mp3")
        return out_path

    monkeypatch.setattr(voice, "google_speak", fake_google)
    voice.edge_tts_speak("문장", tmp_path / "a.mp3")
    assert called["text"] == "문장"


def test_every_failure_is_listed(tmp_path, monkeypatch):
    """무엇을 시도하고 각각 왜 실패했는지 다 보여야 원인을 찾는다."""
    monkeypatch.setattr(voice, "_edge_once", _boom)
    monkeypatch.setattr(voice.time, "sleep", lambda s: None)
    monkeypatch.setenv(voice.ELEVENLABS_KEY_ENV, "만료된키")
    monkeypatch.setattr(voice, "elevenlabs_speak", _boom)
    monkeypatch.setattr(voice, "google_speak", _boom)
    with pytest.raises(voice.VoiceError) as caught:
        voice.edge_tts_speak("문장", tmp_path / "a.mp3")
    message = str(caught.value)
    assert "edge-tts" in message and "일레븐랩스" in message and "구글" in message


# --- 어느 엔진이 읽었나 -------------------------------------------------
#
# 엔진 세 개가 조용히 갈아타는 구조라, 성공한 경로가 로그에 안 남았다.
# 러너에서 edge-tts 가 막히는 것은 이미 알려진 사실이므로, 매일 아침 어떤
# 목소리로 발행되는지 확인할 수단이 없었다는 뜻이다.


def _blocked(*args, **kwargs):
    raise RuntimeError("NoAudioReceived")


def _fake(engine):
    """파일을 남기고 엔진만 기록하는 speak."""
    def speak(text, out_path, voice_name=None):
        Path(out_path).write_bytes(b"")
        voice._record(engine)
        return out_path
    return speak


def test_edge_is_recorded_when_it_speaks(monkeypatch, tmp_path):
    voice.reset_engines()
    monkeypatch.setattr(voice, "_edge_once", lambda text, path, name: path)

    voice.edge_tts_speak("안녕하세요.", tmp_path / "a.mp3")

    assert voice.engines_used() == {voice.EDGE: 1}


def test_records_the_engine_that_spoke_not_the_one_tried_first(monkeypatch, tmp_path):
    """러너에서 실제로 일어나는 일이다. 막히면 조용히 내려간다."""
    voice.reset_engines()
    monkeypatch.setattr(voice, "EDGE_ATTEMPTS", 1)
    monkeypatch.setattr(voice, "_edge_once", _blocked)
    monkeypatch.delenv(voice.ELEVENLABS_KEY_ENV, raising=False)
    monkeypatch.setattr(voice, "google_speak", lambda text, path: path)

    voice.edge_tts_speak("안녕하세요.", tmp_path / "a.mp3")

    assert voice.engines_used() == {voice.GOOGLE: 1}


def test_records_elevenlabs_when_the_key_is_present(monkeypatch, tmp_path):
    voice.reset_engines()
    monkeypatch.setattr(voice, "EDGE_ATTEMPTS", 1)
    monkeypatch.setattr(voice, "_edge_once", _blocked)
    monkeypatch.setenv(voice.ELEVENLABS_KEY_ENV, "키가-있다")
    monkeypatch.setattr(voice, "elevenlabs_speak", lambda text, path: path)

    voice.edge_tts_speak("안녕하세요.", tmp_path / "a.mp3")

    assert voice.engines_used() == {voice.ELEVENLABS: 1}


def test_narrate_flags_a_fallback_so_it_is_not_buried(tmp_path):
    scenes = [Scene("1. 오프닝", "화면", "가"), Scene("7. 엔딩", "화면", "나")]
    lines = []

    voice.narrate(scenes, tmp_path, speak=_fake(voice.GOOGLE), log=lines.append)

    assert any("구글 번역 음성 2개" in line for line in lines)
    # 느낌표가 없으면 로그 수십 줄 사이에 묻힌다. 저장소의 다른 경고와 같은 표기다.
    assert any(line.lstrip().startswith("!") for line in lines)


def test_narrate_does_not_cry_wolf_when_edge_worked(tmp_path):
    lines = []

    voice.narrate([Scene("s", "화면", "가")], tmp_path,
                  speak=_fake(voice.EDGE), log=lines.append)

    assert any("edge-tts 1개" in line for line in lines)
    assert not any(line.lstrip().startswith("!") for line in lines)


def test_counts_do_not_leak_from_the_previous_video(tmp_path):
    """앞 영상의 집계가 남으면 멀쩡한 영상이 대체 음성을 쓴 것처럼 보인다."""
    voice.narrate([Scene("s", "화면", "가")], tmp_path, speak=_fake(voice.GOOGLE))
    voice.narrate([Scene("s", "화면", "가")], tmp_path, speak=_fake(voice.EDGE))

    assert voice.engines_used() == {voice.EDGE: 1}
