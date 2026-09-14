"""롱폼 대본의 "숏폼 컷" 지시를 실제 세로 영상으로 만든다.

`script_parse.shorts_cuts()`는 지금까지 편집자가 눈으로 보고 잘라내는 지시문
텍스트만 돌려줬다. 여기서는 그 지시문(시작 문구 ~ 끝 문구)을 장면 목록에
그대로 대입해 자동으로 잘라낸다 — 화면 문구를 새로 짓지 않는다는 채널 원칙과
같은 이유로, 문구도 새로 판단하지 않고 대본에 있는 것만 그대로 찾는다.
못 찾으면 추측하지 않고 에러를 낸다.
"""

import re
import tempfile
from pathlib import Path

from src import render, script_parse, voice

CUT_RE = re.compile(
    r'컷\s*\d+\s*[:：]\s*["“](.+?)["”]\s*부터\s*["“](.+?)["”]\s*까지'
)


class CutNotFoundError(ValueError):
    """대본 나레이션에서 숏폼 컷의 시작/끝 문구를 찾지 못했다."""


def parse_cuts(script_text):
    """"숏폼 컷 N개" 섹션에서 (시작 문구, 끝 문구) 목록을 뽑는다."""
    cuts = []
    for line in script_parse.shorts_cuts(script_text):
        match = CUT_RE.search(line)
        if match:
            cuts.append((match.group(1).strip(), match.group(2).strip()))
    return cuts


def select_scenes(scenes, start_phrase, end_phrase):
    """시작 문구가 나오는 장면부터 끝 문구가 나오는 장면까지(포함) 잘라낸다."""
    start_index = next(
        (i for i, scene in enumerate(scenes) if start_phrase in scene.narration), None
    )
    if start_index is None:
        raise CutNotFoundError(f"시작 문구를 찾지 못했다: {start_phrase!r}")
    end_index = next(
        (i for i in range(start_index, len(scenes)) if end_phrase in scenes[i].narration),
        None,
    )
    if end_index is None:
        raise CutNotFoundError(f"끝 문구를 찾지 못했다(시작 이후 구간): {end_phrase!r}")
    return scenes[start_index : end_index + 1]


def build(script_text, outdir, stem, speak, voice_name, cut_index=0, log=print):
    """지정한 숏폼 컷 하나를 세로 영상으로 만든다. 영상 경로를 돌려준다."""
    scenes = script_parse.scenes(script_text)
    cuts = parse_cuts(script_text)
    if not cuts:
        raise ValueError("대본에서 '숏폼 컷' 섹션을 찾지 못했다.")
    if cut_index >= len(cuts):
        raise IndexError(f"컷 {cut_index + 1}번이 없다. 대본에 {len(cuts)}개뿐이다.")

    start_phrase, end_phrase = cuts[cut_index]
    cut_scenes = select_scenes(scenes, start_phrase, end_phrase)

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    log(f"숏폼 컷 {cut_index + 1}: 장면 {len(cut_scenes)}개")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        audio_paths = voice.narrate(cut_scenes, tmp, speak=speak, voice=voice_name)
        parts = []
        total = 0.0
        for index, (scene, audio) in enumerate(zip(cut_scenes, audio_paths), start=1):
            image = render.slide(
                scene.screen_text, scene.section, tmp / f"short_slide_{index:03d}.png",
                width=render.SHORT_WIDTH, height=render.SHORT_HEIGHT,
            )
            part = render.mux(image, audio, tmp / f"short_part_{index:03d}.mp4")
            seconds = render.audio_duration(audio)
            total += seconds
            parts.append(part)
            log(f"  {index:>2}/{len(cut_scenes)} {scene.section} · {seconds:5.1f}초")

        video_path = outdir / f"{stem}_short{cut_index + 1}.mp4"
        render.concat(parts, video_path, tmp)

    log(f"숏폼 저장: {video_path}  ({total:.1f}초)")
    return video_path


def build_all(script_text, outdir, stem, speak, voice_name, log=print):
    """대본에 있는 숏폼 컷을 전부 만든다. 문구를 못 찾은 컷은 건너뛰고 계속한다."""
    cuts = parse_cuts(script_text)
    paths = []
    for index in range(len(cuts)):
        try:
            paths.append(build(script_text, outdir, stem, speak, voice_name, index, log))
        except CutNotFoundError as error:
            log(f"  ! 컷 {index + 1}번 건너뜀: {error}")
    return paths
