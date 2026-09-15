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

# 프롬프트가 형식을 못박아도 모델이 그대로 쓴다는 보장이 없고, 검증기는 헤더만 본다.
# 형식이 어긋나면 숏폼이 조용히 0개가 된다 — 실제로 그렇게 한 회차를 날렸다.
# 그래서 라벨 모양을 맞히려 들지 않는다. **섹션 안에 인용된 문장을 순서대로 짝짓는다.**
# 실제로 확인한 모양은 둘이다.
#   컷 1: "시작" 부터 "종료" 까지
#   **컷 1** / 시작: "..." / 종료: "..."
# 세 번째로 0개가 난 회차는 아티팩트를 받지 못해 어떤 모양이었는지 확인하지 못했다.
# 모양을 더 맞혀 보는 대신 짝짓기로 바꾼 이유가 그것이다.
QUOTE = r'["“”\'‘’「」『』]'
QUOTED_RE = re.compile(rf"{QUOTE}\s*(.+?)\s*{QUOTE}")
CUT_ONE_LINE_RE = re.compile(
    rf"{QUOTE}(.+?){QUOTE}\s*(?:부터|에서)\s*{QUOTE}(.+?){QUOTE}\s*까지"
)
# 라벨은 "있으면 참고"하는 정도다. 없어도 등장 순서로 시작·종료를 가른다.
START_LABEL_RE = re.compile(r"(?:시작|첫\s*문장|start)\s*(?:문장|문구)?\s*\**\s*[:：]", re.I)
END_LABEL_RE = re.compile(r"(?:종료|끝|마지막\s*문장|end)\s*(?:문장|문구)?\s*\**\s*[:：]", re.I)
# 컷 뒤에 붙는 군더더기. "(약 20초)" 같은 것이 문장에 섞이면 본문에서 못 찾는다.
TRAILING_NOTE_RE = re.compile(r"\s*[(（][^)）]*[)）]\s*$")
TRIM_CHARS = " \t*-–—~→>\"“”'‘’「」『』"
# 본문과 인용을 맞출 때 무시할 것들. 모델이 따옴표·말줄임·띄어쓰기를 바꿔 옮긴다.
NOISE_RE = re.compile(r"[\s\"“”'‘’.,!?~…·「」『』]")
# 이보다 짧은 조각으로는 느슨하게 맞추지 않는다. 엉뚱한 장면이 걸린다.
MIN_LOOSE_MATCH = 6


class CutNotFoundError(ValueError):
    """대본 나레이션에서 숏폼 컷의 시작/끝 문구를 찾지 못했다."""


def _clean(phrase):
    """인용 문구에서 표기용 군더더기를 걷어낸다."""
    return TRAILING_NOTE_RE.sub("", (phrase or "").strip()).strip(TRIM_CHARS).strip()


def _phrases(line):
    """한 줄에서 시작·종료 후보 문구를 뽑는다. 따옴표가 없으면 라벨 뒤를 쓴다."""
    quoted = [_clean(match.group(1)) for match in QUOTED_RE.finditer(line)]
    quoted = [phrase for phrase in quoted if phrase]
    if quoted:
        return quoted
    label = END_LABEL_RE.search(line) or START_LABEL_RE.search(line)
    if label:
        phrase = _clean(line[label.end():])
        if phrase:
            return [phrase]
    return []


def parse_cuts(script_text):
    """"숏폼 컷 N개" 섹션에서 (시작 문구, 끝 문구) 목록을 뽑는다.

    라벨을 못 알아봐도 인용된 문장이 둘 있으면 컷으로 본다. 잘못 짝지은 컷은
    본문에서 문구를 못 찾아 `build_all` 이 건너뛴다 — 형식을 좁게 잡아 전부
    놓치는 것보다 낫다.
    """
    cuts = []
    pending = None
    for line in script_parse.shorts_cuts(script_text):
        one_line = CUT_ONE_LINE_RE.search(line)
        if one_line:
            cuts.append((_clean(one_line.group(1)), _clean(one_line.group(2))))
            pending = None
            continue

        phrases = _phrases(line)
        if len(phrases) >= 2:
            cuts.append((phrases[0], phrases[1]))
            pending = None
            continue
        if not phrases:
            continue

        phrase = phrases[0]
        looks_like_start = bool(START_LABEL_RE.search(line))
        if pending is not None and not looks_like_start:
            cuts.append((pending, phrase))
            pending = None
        else:
            pending = phrase
    return cuts


def has_section(script_text):
    """숏폼 컷 섹션이 있기는 한지. 컷 0개가 '섹션이 없어서'인지 '형식이 달라서'인지 가른다."""
    return bool(script_parse.shorts_cuts(script_text))


def _find_scene(scenes, phrase, first=0):
    """문구가 들어 있는 첫 장면의 번호. 없으면 None.

    그대로 찾는 것이 먼저다. 못 찾으면 띄어쓰기·따옴표·문장부호만 지우고 다시 본다 —
    모델이 본문을 옮겨 적으면서 그런 것들을 바꾸는 일이 잦다. 다만 짧은 조각까지
    느슨하게 맞추면 엉뚱한 장면이 걸리므로 길이가 되는 것만 그렇게 한다.
    """
    for index in range(first, len(scenes)):
        if phrase in scenes[index].narration:
            return index
    needle = NOISE_RE.sub("", phrase)
    if len(needle) < MIN_LOOSE_MATCH:
        return None
    for index in range(first, len(scenes)):
        if needle in NOISE_RE.sub("", scenes[index].narration):
            return index
    return None


def select_scenes(scenes, start_phrase, end_phrase):
    """시작 문구가 나오는 장면부터 끝 문구가 나오는 장면까지(포함) 잘라낸다."""
    start_index = _find_scene(scenes, start_phrase)
    if start_index is None:
        raise CutNotFoundError(f"시작 문구를 찾지 못했다: {start_phrase!r}")
    end_index = _find_scene(scenes, end_phrase, start_index)
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
