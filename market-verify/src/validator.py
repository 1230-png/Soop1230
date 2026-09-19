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
OPENING_HEADER = "## 1. 오프닝"

# 오프닝은 오랫동안 "물음표로 끝나는 질문 한 문장"이었고, 그 규칙은 프롬프트에만
# 있었다. 지키는지 아무도 보지 않았다는 뜻이다. 사실 한 줄을 앞에 세우도록
# 풀어 주면서 여기로 가져온다 — 규칙 판정은 코드가 한다는 원칙이 이 칸에도 걸린다.
#
# 코드가 판정할 수 있는 것은 둘뿐이다. 질문이 남아 있는가, 그리고 훅이 요약으로
# 자라지 않았는가. "결과를 먼저 말하지 않는다"는 문장 뜻을 읽어야 해서 여기서
# 가리지 못한다 — 그건 프롬프트에 남긴다.
OPENING_MAX_CHARS = 220

# 헤더와 목록 번호를 지워도 본문에 남는 구조 숫자는 숏폼 컷 번호뿐이다.
# ("컷 1:"은 줄 첫머리가 아니라 목록 번호로 지워지지 않는다.)
# 여기에 숫자를 더 넣을수록 환각 탐지가 그만큼 헐거워진다.
STRUCTURAL_NUMBERS = frozenset({"1", "2", "3"})

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
LIST_MARKER_RE = re.compile(r"^\s*\d+[.)]\s+")
# 마크다운 구분선. 운영자 칸에 이게 있어도 사람이 쓴 코멘트는 아니다.
HORIZONTAL_RULE_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", re.MULTILINE)
# HTML 주석. 렌더링되지 않으므로 시청자에게 보이지 않는다.
# 저장할 때 넣는 작성 안내가 여기 들어가며, 그건 운영자 코멘트가 아니다.
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# 화면 표기는 읽지 않는다. 오프닝 길이를 잴 때 같이 세면 안 된다.
VISUAL_CUE_RE = re.compile(r"\[자료 화면:.*?\]", re.DOTALL)


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


def _block_numbers(block):
    """블록이 허용하는 숫자.

    날짜는 통째로 걷어내고 세지만, 연도만은 따로 넣어 준다.
    "1990-01-02 ~ 2026-09-04" 를 두고 대본이 "1990년부터"라고 쓰는 것은
    지어낸 수치가 아니라 블록에 적힌 연도를 그대로 부른 것이다.
    월·일은 넣지 않는다. 그건 날짜를 그대로 인용하면 될 일이다.
    """
    numbers = _extract_numbers(block)
    numbers.update(date[:4] for date in DATE_RE.findall(block))
    return numbers


def _number_contexts(text):
    """숫자마다 처음 등장한 문장을 기억한다.

    "블록에 없는 숫자: 36" 만 돌려주면 모델이 어디를 고쳐야 할지 모른다.
    재시도할 때 문장을 같이 보여줘야 고칠 수 있다.
    """
    contexts = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for token in NUMBER_RE.findall(DATE_RE.sub(" ", line)):
            contexts.setdefault(_normalize_number(token), stripped[:80])
    return contexts


def _section_body(script, header):
    """헤더 아래부터 다음 헤더 전까지. 헤더가 없으면 None(누락은 따로 잡는다)."""
    start = script.find(header)
    if start == -1:
        return None
    after = script[start + len(header):]
    next_header = re.search(r"^##\s", after, re.MULTILINE)
    body = after[: next_header.start()] if next_header else after
    return body


def _opening_violations(script):
    """오프닝이 훅 자리를 지키는지. 질문이 있어야 하고, 요약만큼 길면 안 된다."""
    body = _section_body(script, OPENING_HEADER)
    if body is None:
        return []
    text = VISUAL_CUE_RE.sub("", HTML_COMMENT_RE.sub("", body)).strip()
    if not text:
        return [f"{OPENING_HEADER} 이 비어 있다."]

    found = []
    if "?" not in text and "？" not in text:
        found.append(
            f"{OPENING_HEADER} 에 질문이 없다. 물음표로 끝나는 질문 한 문장으로 닫을 것."
        )
    if len(text) > OPENING_MAX_CHARS:
        found.append(
            f"{OPENING_HEADER} 이 {len(text)}자다. {OPENING_MAX_CHARS}자 이내로 줄일 것 — "
            "사실 한 문장과 질문 한 문장이면 된다."
        )
    return found


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

    body = _section_body(script, OPERATOR_HEADER)
    if body is not None:
        # 구분선과 HTML 주석은 지우고 본다. 둘 다 코멘트 본문이 아니다.
        body = HORIZONTAL_RULE_RE.sub("", HTML_COMMENT_RE.sub("", body))
    if body is not None and body.strip():
        violations.append(
            f"{OPERATOR_HEADER} 섹션은 비워야 한다. 사람이 채우는 칸이다. "
            f"작성된 내용: {body.strip()[:60]}"
        )

    violations += _opening_violations(script)

    block_dates = set(DATE_RE.findall(block))
    for date in sorted(set(DATE_RE.findall(script))):
        if date not in block_dates:
            violations.append(f"데이터 블록에 없는 날짜: {date}")

    stripped_script = _strip_structural_text(script)
    block_numbers = _block_numbers(block)
    script_numbers = _extract_numbers(stripped_script)
    unknown = script_numbers - block_numbers - STRUCTURAL_NUMBERS
    contexts = _number_contexts(stripped_script) if unknown else {}
    for number in sorted(unknown, key=float):
        context = contexts.get(number)
        detail = f' (해당 문장: "{context}")' if context else ""
        violations.append(f"데이터 블록에 없는 숫자: {number}{detail}")

    return violations
