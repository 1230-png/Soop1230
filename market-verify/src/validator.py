"""대본이 채널 규칙을 지켰는지 코드로 검증한다.

모델의 자체 점검은 신뢰하지 않는다. 위반해놓고 통과했다고 답하기 때문에
합격/불합격 판정은 전부 이 모듈이 내린다.
"""

import re

REQUIRED_HEADERS = [
    "## 제목 3안",
    "## 1. 오프닝",
    "## 2. 조건 설정",
    "## 3. 과거 사례",
    "## 4. 결과",
    "## 5. 데이터의 한계",
    "## 6. [운영자 코멘트]",
    "## 7. 엔딩",
    "## 숏폼 컷 3개",
    "## 유튜브 설명란",
]

BANNED_WORDS = ["폭락", "급락", "급등", "떡상", "대폭", "사상 최악", "충격", "지금 당장"]

REQUIRED_PHRASES = ["판단은 각자", "투자 권유나 조언이 아닙니다"]

VISUAL_CUE = "[자료 화면:"
MIN_VISUAL_CUES = 5

OPERATOR_HEADER = "## 6. [운영자 코멘트]"

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
LIST_MARKER_RE = re.compile(r"^\s*\d+[.)]\s+")


def _normalize_number(token):
    value = float(token)
    if value == int(value):
        return str(int(value))
    return f"{value:.10f}".rstrip("0").rstrip(".")


def _strip_structural_text(text):
    """숫자 대조 전에 헤더 줄과 목록 번호를 지운다.

    "## 1. 오프닝"의 1이나 목록의 "3. "을 대본 수치로 세면 오탐이 난다.
    """
    kept = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        kept.append(LIST_MARKER_RE.sub("", line))
    return "\n".join(kept)


def _extract_numbers(text):
    without_dates = DATE_RE.sub(" ", text)
    return {_normalize_number(tok) for tok in NUMBER_RE.findall(without_dates)}


def _operator_section_body(script):
    start = script.find(OPERATOR_HEADER)
    if start == -1:
        return None
    after = script[start + len(OPERATOR_HEADER):]
    next_header = re.search(r"^##\s", after, re.MULTILINE)
    body = after[: next_header.start()] if next_header else after
    return body


def validate(script, block):
    """위반 목록을 돌려준다. 통과하면 빈 리스트."""
    violations = []

    for header in REQUIRED_HEADERS:
        if header not in script:
            violations.append(f"필수 헤더 누락: {header}")

    for word in BANNED_WORDS:
        if word in script:
            violations.append(f"금지어 사용: {word}")

    for phrase in REQUIRED_PHRASES:
        if phrase not in script:
            violations.append(f"필수 문구 누락: {phrase}")

    cue_count = script.count(VISUAL_CUE)
    if cue_count < MIN_VISUAL_CUES:
        violations.append(
            f'"{VISUAL_CUE}" 표기가 {cue_count}개다. {MIN_VISUAL_CUES}개 이상 필요하다.'
        )

    body = _operator_section_body(script)
    if body is not None and body.strip():
        violations.append(
            f"{OPERATOR_HEADER} 섹션은 비워야 한다. 사람이 채우는 칸이다. "
            f"작성된 내용: {body.strip()[:60]}"
        )

    block_dates = set(DATE_RE.findall(block))
    for date in sorted(set(DATE_RE.findall(script))):
        if date not in block_dates:
            violations.append(f"데이터 블록에 없는 날짜: {date}")

    block_numbers = _extract_numbers(block)
    script_numbers = _extract_numbers(_strip_structural_text(script))
    for number in sorted(script_numbers - block_numbers, key=float):
        violations.append(f"데이터 블록에 없는 숫자: {number}")

    return violations
