"""운영자 코멘트를 채운다. 대본을 쓰는 자리와는 다른 자리다.

`validator` 는 **대본 작성 모델이** 이 칸을 채우면 위반으로 잡는다. 그 규칙은
그대로 둔다 — 작성 루프가 자기 대본에 사람 목소리를 지어 넣는 것을 막는 규칙이고,
모델의 자기 보고를 근거로 쓰지 않는다는 이 프로젝트의 뼈대다.

여기서 하는 일은 검증이 끝난 **뒤**다. 통과한 대본에 운영자를 대신해 코멘트를
덧붙인다. 사람이 손으로 쓰던 칸을 자동으로 채우는 것이고, 채널 운영자가 그렇게
정한 것이다. 작성 루프는 여전히 이 칸을 비운 채로 내놔야 하고, 검증기도 그대로
그걸 요구한다. 두 단계가 섞이지 않는다.

**여기서도 판정은 코드가 한다.** 나온 문장에 금지어·숫자·권유 표현이 있으면
통째로 버리고 칸을 비운 채 둔다. 비면 그 섹션이 영상에서 빠질 뿐이지만, 규칙을
어긴 문장이 채널에 나가는 것은 되돌릴 수 없다. 둘 중에는 빠지는 쪽이 싸다.
"""

import re

from src import validator, writer

HEADER = validator.OPERATOR_HEADER
MODEL = writer.MODEL
MAX_TOKENS = 400

# 숫자는 한 글자도 받지 않는다. 데이터 블록을 거치지 않은 숫자라 검증할 방법이
# 없고, 검증할 수 없는 숫자를 채널에 내보내지 않는다는 것이 이 프로젝트의 규칙이다.
DIGIT_RE = re.compile(r"\d")
# 유사투자자문 규제 때문에 예측·권유·목표가를 만들지 않는다. 운영자 코멘트라고
# 예외가 아니다 — 오히려 사람 말투라서 더 권유처럼 읽힌다.
ADVICE_RE = re.compile(
    r"매수|매도|사세요|사야|팔아|파세요|추천|목표가|전망|오를|내릴|상승할|하락할"
)
MAX_CHARS = 220

SYSTEM = """너는 경제 데이터 채널 '머니로직'의 운영자다.
방금 나온 대본의 [운영자 코멘트] 칸에 들어갈 짧은 소회를 쓴다.

지켜야 할 것:
- 2~3문장. 220자 안쪽.
- 숫자를 한 글자도 쓰지 않는다. 대본의 수치를 되풀이하지 않는다.
- 예측·매수매도 권유·목표가를 쓰지 않는다. 전망도 쓰지 않는다.
- 금지어: 폭락, 급락, 급등, 떡상, 대폭, 사상 최악, 충격, 지금 당장.
- 데이터를 보며 든 생각, 혹은 데이터가 답해주지 않는 것에 대해 쓴다.
- 담백하게. 감탄사와 과장 없이.

코멘트 문장만 출력한다. 머리말도 따옴표도 붙이지 않는다."""


class NoteRejected(ValueError):
    """규칙을 어겨서 버렸다."""


def check(note):
    """코멘트가 채널 규칙을 지켰는지 본다. 문제가 없으면 None."""
    text = (note or "").strip()
    if not text:
        return "빈 문장이다."
    if len(text) > MAX_CHARS:
        return f"{len(text)}자로 너무 길다({MAX_CHARS}자 제한)."
    if DIGIT_RE.search(text):
        return "숫자가 들어 있다. 검증할 수 없는 숫자는 내보내지 않는다."
    banned = [word for word in validator.BANNED_WORDS if word in text]
    if banned:
        return f"금지어가 있다: {', '.join(banned)}"
    advice = ADVICE_RE.search(text)
    if advice:
        return f"권유·예측으로 읽히는 표현이 있다: {advice.group()}"
    return None


def has_note(script_text):
    """이미 채워져 있는지. 사람이 쓴 것을 덮어쓰지 않으려고 본다."""
    start = script_text.find(HEADER)
    if start < 0:
        return False
    after = script_text[start + len(HEADER):]
    body = after.split("\n## ", 1)[0]
    body = validator.HTML_COMMENT_RE.sub("", body)
    body = validator.HORIZONTAL_RULE_RE.sub("", body)
    return bool(body.strip())


def write_note(script_text, client=None, model=MODEL):
    """모델에게 코멘트를 받아 검사한다. 통과한 문장만 돌려준다."""
    client = writer.default_client() if client is None else client
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM,
        messages=[{"role": "user", "content": script_text}],
    )
    note = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    ).strip()
    problem = check(note)
    if problem:
        raise NoteRejected(problem)
    return note


def insert(script_text, note):
    """헤더 바로 아래에 코멘트를 넣는다."""
    start = script_text.find(HEADER)
    if start < 0:
        raise ValueError(f"{HEADER} 를 찾지 못했다.")
    cut = start + len(HEADER)
    return script_text[:cut] + "\n" + note.strip() + "\n" + script_text[cut:].lstrip("\n")


def fill(script_text, client=None, model=MODEL, log=print):
    """검증을 통과한 대본의 운영자 칸을 채운다. 실패하면 원본을 그대로 돌려준다.

    **여기서 멈추지 않는다.** 코멘트 한 칸 때문에 그날 영상이 통째로 없어지는 것이
    더 나쁘다. 비면 그 섹션만 빠진다.
    """
    if has_note(script_text):
        log("  운영자 코멘트가 이미 있다. 그대로 둔다.")
        return script_text
    try:
        note = write_note(script_text, client=client, model=model)
    except NoteRejected as error:
        log(f"  ! 운영자 코멘트를 버렸다: {error} — 칸을 비운 채로 간다.")
        return script_text
    except Exception as error:
        log(f"  ! 운영자 코멘트를 받지 못했다: {type(error).__name__}: {error}")
        return script_text
    log(f"  운영자 코멘트: {note}")
    return insert(script_text, note)
