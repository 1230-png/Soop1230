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


# 모델이 실제로 쓴 형식. 프롬프트가 형식을 못박지 않아 픽스처와 다르게 나왔고,
# 예전 파서는 이걸 한 컷도 못 읽었다. 그때 숏폼이 조용히 0개가 됐다.
REAL_FORMAT = SCRIPT.replace(
    '컷 1: "주간 종가가 3주 연속 하락한 뒤, 지수는 어떻게 움직였을까요?" 부터 '
    '"출처는 Yahoo Finance이고, 수정주가 기준입니다." 까지',
    '**컷 1**\n시작: "주간 종가가 3주 연속 하락한 뒤, 지수는 어떻게 움직였을까요?"\n'
    '종료: "출처는 Yahoo Finance이고, 수정주가 기준입니다."',
)


def test_parse_cuts_reads_the_format_the_model_actually_writes():
    """프롬프트가 형식을 못박지 않는다. 검증기도 헤더만 본다. 파서가 받아줘야 한다."""
    cuts = shorts.parse_cuts(REAL_FORMAT)
    assert len(cuts) == 3
    assert cuts[0][0].startswith("주간 종가가 3주 연속 하락한 뒤")
    assert cuts[0][1] == "출처는 Yahoo Finance이고, 수정주가 기준입니다."


BODY = SCRIPT.split(script_parse.SHORTS_HEADER)[0]
START = "주간 종가가 3주 연속 하락한 뒤, 지수는 어떻게 움직였을까요?"
END = "출처는 Yahoo Finance이고, 수정주가 기준입니다."


def with_cut_section(body_lines):
    """숏폼 컷 섹션만 갈아끼운 대본."""
    return (
        BODY + script_parse.SHORTS_HEADER + "\n" + body_lines
        + "\n## 유튜브 설명란\n설명.\n"
    )


# 형식을 프롬프트에 못박아도 모델이 지킨다는 보장이 없다. 한 회차가 통째로
# 숏폼 0개로 끝난 적이 있어, 본 적 있는 모양과 있을 법한 모양을 전부 세워 둔다.
CUT_SECTION_FORMATS = {
    "대시 + 라벨": f'- 컷 1\n- 시작 문장: "{START}"\n- 종료 문장: "{END}"\n',
    "굵은 라벨": f'**컷 1**\n**시작**: "{START}"\n**종료**: "{END}"\n',
    "화살표 한 줄": f'컷 1: "{START}" → "{END}"\n',
    "라벨 없이 인용만": f'### 컷 1 (훅 구간)\n"{START}"\n"{END}"\n',
    "따옴표 없이 라벨만": f"컷 1\n시작: {START}\n종료: {END}\n",
    "인용 뒤 괄호 주석": f'컷 1\n시작: "{START}" (약 20초)\n종료: "{END}"\n',
}


@pytest.mark.parametrize("label", sorted(CUT_SECTION_FORMATS))
def test_parse_cuts_survives_whatever_shape_the_model_writes(label):
    cuts = shorts.parse_cuts(with_cut_section(CUT_SECTION_FORMATS[label]))
    assert cuts == [(START, END)], f"{label} 형식을 읽지 못했다"


# 실제 12회차 컷들의 장면 길이. 모델은 "60초 이내"를 지키지 못한다 — 잴 수가 없다.
RUN12_CUT1 = [7.7, 28.8, 16.3, 12.9, 27.6, 4.6, 30.2]   # 합 128.1초
RUN12_CUT2 = [40.7]                                      # 이미 60초 안
RUN12_CUT3 = [72.0, 49.3, 2.4]                           # 첫 장면이 혼자 72초


def test_fit_to_limit_trims_the_tail_of_an_overlong_cut():
    kept = shorts.fit_to_limit(RUN12_CUT1, max_seconds=60)
    assert kept == 3
    assert sum(RUN12_CUT1[:kept]) <= 60


def test_fit_to_limit_leaves_a_cut_that_already_fits():
    assert shorts.fit_to_limit(RUN12_CUT2, max_seconds=60) == 1


def test_fit_to_limit_keeps_one_scene_even_when_it_alone_overflows():
    """자를 데가 없으면 빈 영상을 만들지 않는다. 그대로 두고 로그로 알린다."""
    assert shorts.fit_to_limit(RUN12_CUT3, max_seconds=60) == 1


def test_fit_to_limit_handles_no_scenes():
    assert shorts.fit_to_limit([], max_seconds=60) == 0


def test_select_scenes_matches_across_punctuation_the_model_changed():
    """모델이 본문을 옮기며 따옴표·띄어쓰기를 바꾼다. 그 정도로는 놓치지 않는다."""
    scenes = script_parse.scenes(SCRIPT)
    start, end = shorts.parse_cuts(SCRIPT)[0]
    loosened = start.replace(", ", ",").rstrip("?")
    selected = shorts.select_scenes(scenes, loosened, end)
    assert selected[0].section == "1. 오프닝"
    assert start in selected[0].narration


def test_select_scenes_still_refuses_a_short_fragment():
    """느슨하게 맞추더라도 짧은 조각으로 엉뚱한 장면을 잡지 않는다."""
    scenes = script_parse.scenes(SCRIPT)
    with pytest.raises(shorts.CutNotFoundError):
        shorts.select_scenes(scenes, "없는말", "판단은 각자.")


def test_has_section_separates_missing_from_unreadable():
    assert shorts.has_section(SCRIPT) is True
    assert shorts.has_section("## 1. 오프닝\n한 문장.\n") is False


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
    assert start in selected[0].narration
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


def test_build_trims_a_cut_that_runs_over_the_limit(tmp_path):
    """상한을 넘으면 뒤 장면을 빼고 실제로 짧은 영상이 나와야 한다.

    fit_to_limit 의 산수만 맞아서는 소용이 없다. 잘라낸 장면 수만큼 concat 에
    넘기는 조각도 줄어야 한다.
    """
    full = shorts.build(
        FILLED, tmp_path, "full", voice.silent_speak, voice.DEFAULT_VOICE,
        cut_index=0, log=lambda *a: None, max_seconds=999,
    )
    # 상한은 첫 장면보다 길고 전체보다는 짧아야 자를 자리가 있다. 절반으로
    # 잡아 두면 첫 장면이 길어진 날 이 시험이 대신 깨진다 — 실제로 그랬다.
    # (상한이 첫 장면보다 짧은 경우는 바로 아래 시험이 따로 본다.)
    one_scene = shorts.build(
        FILLED, tmp_path, "one", voice.silent_speak, voice.DEFAULT_VOICE,
        cut_index=0, log=lambda *a: None, max_seconds=0.1,
    )
    limit = (render.audio_duration(one_scene) + render.audio_duration(full)) / 2
    trimmed = shorts.build(
        FILLED, tmp_path, "trim", voice.silent_speak, voice.DEFAULT_VOICE,
        cut_index=0, log=lambda *a: None, max_seconds=limit,
    )
    assert render.audio_duration(trimmed) < render.audio_duration(full)
    assert render.audio_duration(trimmed) <= limit
    # 잘라도 세로 규격은 그대로다.
    assert _dimensions(trimmed) == (render.SHORT_WIDTH, render.SHORT_HEIGHT)


def test_build_keeps_the_first_scene_even_under_an_impossible_limit(tmp_path):
    """상한이 첫 장면보다 짧아도 빈 영상을 만들지 않는다."""
    path = shorts.build(
        FILLED, tmp_path, "tiny", voice.silent_speak, voice.DEFAULT_VOICE,
        cut_index=0, log=lambda *a: None, max_seconds=0.1,
    )
    assert path.exists()
    assert render.audio_duration(path) > 1


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
