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
