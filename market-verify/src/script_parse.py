"""검증을 통과한 대본을 영상 장면 목록으로 쪼갠다.

대본에는 이미 [자료 화면: 내용 / 화면 텍스트 "..."] 표기가 들어 있다.
그 표기가 장면 경계이자 화면에 띄울 문구다. 따로 만들 필요가 없다.
"""

import re

NARRATED_SECTIONS = [
    "## 1. 오프닝",
    "## 2. 조건 설정",
    "## 3. 과거 사례",
    "## 4. 결과",
    "## 5. 데이터의 한계",
    "## 6. [운영자 코멘트]",
    "## 7. 엔딩",
]
TITLE_HEADER = "## 제목 3안"
DESCRIPTION_HEADER = "## 유튜브 설명란"
SHORTS_HEADER = "## 숏폼 컷 3개"

CUE_RE = re.compile(r"\[자료 화면:\s*(.*?)\]", re.DOTALL)
SCREEN_TEXT_RE = re.compile(r"화면 텍스트\s*[:：]?\s*[\"“](.+?)[\"”]", re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
LIST_MARKER_RE = re.compile(r"^\s*\d+[.)]\s*")


class Scene:
    """한 장면. 화면에 띄울 문구 하나와 그 위에서 읽을 나레이션."""

    def __init__(self, section, screen_text, narration):
        self.section = section
        self.screen_text = screen_text
        self.narration = narration

    def __repr__(self):
        return f"Scene({self.section!r}, {self.screen_text!r}, {self.narration[:20]!r})"

    def __eq__(self, other):
        return (
            isinstance(other, Scene)
            and (self.section, self.screen_text, self.narration)
            == (other.section, other.screen_text, other.narration)
        )


def _section_of(line):
    for header in NARRATED_SECTIONS:
        if line.strip() == header:
            return header.replace("## ", "")
    return None


def _cue_screen_text(cue_body):
    """[자료 화면: ...] 안에서 화면에 띄울 문구를 뽑는다."""
    match = SCREEN_TEXT_RE.search(cue_body)
    if match:
        return match.group(1).strip()
    # "화면 텍스트" 표기가 없으면 슬래시 뒤쪽, 그것도 없으면 전체를 쓴다.
    tail = cue_body.split("/")[-1].strip()
    return tail or cue_body.strip()


def titles(script):
    """제목 3안. 첫 번째를 영상 제목으로 쓴다."""
    found = []
    collecting = False
    for line in script.splitlines():
        if line.strip() == TITLE_HEADER:
            collecting = True
            continue
        if collecting:
            if line.startswith("## "):
                break
            text = LIST_MARKER_RE.sub("", line).strip()
            if text:
                found.append(text)
    return found


def description(script):
    """유튜브 설명란 본문."""
    lines = []
    collecting = False
    for line in script.splitlines():
        if line.strip() == DESCRIPTION_HEADER:
            collecting = True
            continue
        if collecting:
            if line.startswith("## "):
                break
            lines.append(line.rstrip())
    return "\n".join(lines).strip()


def shorts_cuts(script):
    """숏폼 컷 지시. 영상에는 쓰지 않고 편집자가 본다."""
    lines = []
    collecting = False
    for line in script.splitlines():
        if line.strip() == SHORTS_HEADER:
            collecting = True
            continue
        if collecting:
            if line.startswith("## "):
                break
            if line.strip():
                lines.append(line.strip())
    return lines


def scenes(script):
    """나레이션 구간을 장면 단위로 쪼갠다.

    대본은 [자료 화면:] 을 그것이 설명하는 문장 "뒤"에 붙인다.
    그래서 표기를 만나면 직전까지 쌓인 나레이션에 그 화면 문구를 씌운다.
    표기가 문단보다 먼저 나오면(섹션 첫 줄 등) 뒤따르는 나레이션에 씌운다.
    어느 쪽도 아니면 섹션 제목을 띄운다.
    """
    script = HTML_COMMENT_RE.sub("", script)
    result = []
    section = None
    screen_text = None
    buffer = []

    def flush(cue_text=None):
        if section and buffer:
            text = " ".join(buffer).strip()
            if text:
                result.append(Scene(section, cue_text or screen_text or section, text))
        buffer.clear()

    for raw in script.splitlines():
        line = raw.strip()
        found = _section_of(raw)
        if found:
            flush()
            section = found
            screen_text = found
            continue
        if line.startswith("## "):
            flush()
            section = None
            continue
        if section is None or not line:
            continue
        cue = CUE_RE.search(line)
        if cue:
            cue_text = _cue_screen_text(cue.group(1))
            if buffer:
                # 방금 읽은 문장을 설명하는 표기다. 그 문장에 씌운다.
                flush(cue_text)
                screen_text = section
            else:
                # 문단보다 먼저 나왔다. 뒤따르는 나레이션에 씌운다.
                screen_text = cue_text
            leftover = CUE_RE.sub("", line).strip()
            if leftover:
                buffer.append(leftover)
            continue
        buffer.append(LIST_MARKER_RE.sub("", line))

    flush()
    return result


def narration_text(script):
    """전체 나레이션. 길이 가늠용."""
    return " ".join(scene.narration for scene in scenes(script))
