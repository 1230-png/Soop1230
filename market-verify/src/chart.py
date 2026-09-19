"""데이터 블록에서 그림에 쓸 숫자를 뽑는다. 그리기는 render.py 가 한다.

이 채널이 가진 유일한 자산은 실측 분포다. NOTES.md 도 CLAUDE.md 도 "평균이 아니라
분포를 먼저 말한다"를 규칙으로 두고 있다. 그런데 그 분포를 글자로만 읽어 주고
있었다 — 63건이 어디에 몰려 있고 어디까지 벌어졌는지는 그림 한 장이면 보이는데,
소리로는 안 보인다.

**숫자를 여기서 새로 만들지 않는다.** market_events.py 가 이미 낸 블록을 읽기만
한다. 그리는 값과 대본이 말하는 값이 갈라지면 안 되기 때문이다 — 블록이 유일한
출처라는 규칙은 그림에도 그대로 적용된다.

그리기(Pillow)와 떼어 놓은 이유가 하나 더 있다. 이 파일은 글자만 다루므로
한글 폰트가 없는 곳에서도 시험이 돈다.
"""

import re
import statistics

CASES_MARKER = "[사례별 이후 수익률 %]"
# 블록의 구간 이름은 "252거래일(12개월)" 꼴이다. 괄호 안이 사람이 읽는 이름이다.
PAREN_RE = re.compile(r"[(（]([^)）]+)[)）]")
# 점이 두엇뿐이면 분포라고 부를 것이 없다. 그때는 글자 화면이 낫다.
MIN_POINTS = 3


def _cells(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _number(text):
    """수익률 한 칸. '데이터 부족' 같은 칸은 None 으로 흘린다."""
    try:
        return float(text)
    except ValueError:
        return None


def _is_rule(cells):
    """마크다운 표의 구분선(| --- | --- |)인가."""
    return bool(cells) and set("".join(cells)) <= set("- :")


def parse_cases(block_text):
    """(구간 이름, 수익률 목록) 을 블록에 적힌 순서대로 돌려준다.

    [사례별 이후 수익률 %] 표만 읽는다. 조건 검증(run.py)과 매크로 검증
    (run_macro.py)이 이 표를 낸다. 전략·토크노믹스 블록에는 이 표가 없어서 빈
    목록이 나오고, 그때 부르는 쪽은 글자 화면으로 돌아간다.

    **못 읽으면 예외를 던지지 않고 빈 목록을 돌려준다.** 사람 확인 없이 공개로
    나가는 파이프라인이라, 그림을 못 그리는 것이 발행을 멈출 이유가 되면 안 된다.
    """
    lines = block_text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == CASES_MARKER:
            start = index
            break
    if start is None:
        return []

    header = None
    rows = []
    for line in lines[start + 1:]:
        stripped = line.strip()
        if not stripped:
            if header is None:
                continue  # 표제와 표 사이의 빈 줄
            break
        if not stripped.startswith("|"):
            break
        cells = _cells(stripped)
        if _is_rule(cells):
            continue
        if header is None:
            header = cells[1:]  # 첫 칸은 발생일
            continue
        rows.append(cells[1:])

    if not header or not rows:
        return []

    series = []
    for index, name in enumerate(header):
        values = [
            value
            for value in (_number(row[index]) for row in rows if index < len(row))
            if value is not None
        ]
        if len(values) >= MIN_POINTS:
            series.append((name, values))
    return series


def median(values):
    return statistics.median(values)


def span(series):
    """모든 구간을 한 축에 놓기 위한 (최저, 최고). 0 은 언제나 축 안에 둔다.

    구간마다 축을 따로 잡으면 눈으로 비교할 수 없다 — 1개월과 12개월이 같은
    폭으로 보이는데 실제로는 배가 차이 나는 일이 생긴다.
    """
    values = [value for _, points in series for value in points]
    if not values:
        return None
    low, high = min(values + [0.0]), max(values + [0.0])
    if low == high:
        return low - 1.0, high + 1.0
    return low, high


def short_name(horizon):
    """'252거래일(12개월)' → '12개월'. 썸네일처럼 폭이 좁은 자리에서 쓴다.

    괄호가 없으면 손대지 않고 그대로 돌려준다 — 블록 형식이 바뀌었을 때
    이름을 지어내는 것보다 길게 나오는 편이 낫다.
    """
    match = PAREN_RE.search(horizon)
    return match.group(1).strip() if match else horizon.strip()
