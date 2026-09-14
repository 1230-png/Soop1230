import json
import subprocess

import pytest

from src import render, script_parse, shorts, voice
from tests.fixtures import SCRIPT

FILLED = SCRIPT.replace(
    "## 6. [운영자 코멘트]\n\n",
    "## 6. [운영자 코멘트]\n저는 그때 데이터를 안 보고 움직였습니다.\n\n",
)


def _dimensions(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return stream["width"], stream["height"]


def test_parse_cuts_reads_every_cut_in_the_script():
    cuts = shorts.parse_cuts(SCRIPT)
    assert len(cuts) == 3
    assert cuts[0][0].startswith("주간 종가가 3주 연속 하락한 뒤")
    assert cuts[0][1] == "출처는 Yahoo Finance이고, 수정주가 기준입니다."


def test_parse_cuts_returns_nothing_without_the_section():
    assert shorts.parse_cuts("## 1. 오프닝\n한 문장.\n") == []


def test_select_scenes_spans_from_the_start_phrase_to_the_end_phrase():
    scenes = script_parse.scenes(SCRIPT)
    start, end = shorts.parse_cuts(SCRIPT)[0]
    selected = shorts.select_scenes(scenes, start, end)
    assert selected[0].narration.startswith("주간 종가가 3주 연속 하락한 뒤")
    assert end in selected[-1].narration
    assert len(selected) < len(scenes), "컷이 대본 전체를 그대로 가져왔다"


def test_select_scenes_refuses_to_guess_when_the_phrase_is_absent():
    scenes = script_parse.scenes(SCRIPT)
    with pytest.raises(shorts.CutNotFoundError):
        shorts.select_scenes(scenes, "대본에 없는 문장", "판단은 각자.")


def test_select_scenes_requires_the_end_phrase_after_the_start():
    scenes = script_parse.scenes(SCRIPT)
    with pytest.raises(shorts.CutNotFoundError):
        # 끝 문구가 시작보다 앞에 있으면 구간이 성립하지 않는다.
        shorts.select_scenes(
            scenes, "표본은 12건입니다.", "주간 종가가 3주 연속 하락한 뒤, 지수는 어떻게 움직였을까요?"
        )


def test_build_makes_a_vertical_short(tmp_path):
    path = shorts.build(
        FILLED, tmp_path, "demo", voice.silent_speak, voice.DEFAULT_VOICE,
        cut_index=0, log=lambda *a: None,
    )
    assert path.exists() and path.suffix == ".mp4"
    assert render.audio_duration(path) > 1
    assert _dimensions(path) == (render.SHORT_WIDTH, render.SHORT_HEIGHT)


def test_build_rejects_a_cut_index_that_does_not_exist(tmp_path):
    with pytest.raises(IndexError):
        shorts.build(FILLED, tmp_path, "demo", voice.silent_speak,
                     voice.DEFAULT_VOICE, cut_index=9, log=lambda *a: None)


def test_build_rejects_a_script_without_a_shorts_section(tmp_path):
    with pytest.raises(ValueError):
        shorts.build("## 1. 오프닝\n한 문장.\n", tmp_path, "demo", voice.silent_speak,
                     voice.DEFAULT_VOICE, log=lambda *a: None)


def test_build_all_makes_every_cut(tmp_path):
    paths = shorts.build_all(
        FILLED, tmp_path, "demo", voice.silent_speak, voice.DEFAULT_VOICE, log=lambda *a: None
    )
    assert len(paths) == 3
    assert len({path.name for path in paths}) == 3, "컷마다 다른 파일이어야 한다"
