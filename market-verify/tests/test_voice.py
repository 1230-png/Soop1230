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


def test_without_a_fallback_key_it_says_why(tmp_path, monkeypatch):
    """무음으로 대신 만들지 않는다. 나레이션 없는 영상이 발행되면 더 나쁘다."""
    monkeypatch.setattr(voice, "_edge_once", _boom)
    monkeypatch.setattr(voice.time, "sleep", lambda s: None)
    monkeypatch.delenv(voice.ELEVENLABS_KEY_ENV, raising=False)
    with pytest.raises(voice.VoiceError, match="ELEVENLABS_API_KEY"):
        voice.edge_tts_speak("문장", tmp_path / "a.mp3")


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
