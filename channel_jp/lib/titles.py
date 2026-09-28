"""제목을 만든다. **구독자 없는 채널이 발견되는 유일한 길이 검색이다.**

왜 이 파일이 생겼는지 — 2026-09-27 측정값 때문이다. 이 채널은 롱폼 8편 중
**7편이 0회**이고 총 3회였다(구독자 7명). 정해진 시각에 꾸준히 냈고 아무도
보지 않았다. 발행된 제목을 늘어놓고 보니 문제가 둘이었다.

**첫째, 같은 제목이 여러 편이다.**

    잠들기 전 일본어 듣기 35분 | 자면서 듣는 일본어 회화 150문장
    잠들기 전 일본어 듣기 35분 | 자면서 듣는 일본어 회화 150문장   ← 똑같다
    잠들기 전 일본어 듣기 36분 | 자면서 듣는 일본어 회화 150문장   ← 한 글자 차이

예전 틀은 `{count}` 와 `{minutes}` 만 바뀌었는데 `phrase_count` 가 팩마다
고정이라 **count 는 늘 같고 minutes 는 한두 값을 오간다.** 그래서 수면 팩은
평생 두 가지 제목, 세 시간 팩은 한 가지 제목만 낸다. 같은 제목끼리는
검색에서 서로를 잡아먹고, 유튜브 쪽에서 보면 **틀을 반복 재생산한 것**으로
읽힌다(CLAUDE.md 가 거르는 기준으로 적어 둔 그것이다).

**둘째, 검색어가 뒤에 있었다.** 검색 결과와 휴대폰 목록에서는 제목 앞부분만
보인다. 「잠들기 전 일본어 듣기 35분」 다음에 오는 「자면서 듣는 일본어」가
실제 검색어인데 잘리는 자리에 있었다.

그래서 규칙 셋.

1. **검색어를 맨 앞에** 둔다. 길이·문장 수는 검색어가 아니므로 뒤로 보낸다
2. **편마다 다른 내용을 제목에 넣는다.** 이 채널은 903문장을 12개 주제에서
   골라 쓰므로 편마다 들어가는 주제 구성이 실제로 다르다. 그것을 적는다 —
   숫자를 붙여 구분하는 것과 달리 **제목이 내용을 말하게 된다**
3. **그래도 겹치면 회차를 붙인다.** 이미 낸 제목과 같은 것을 또 내지 않는다
"""

from __future__ import annotations

import collections

TITLE_MAX = 100          # 유튜브 상한
FOCUS_TOPICS = 3         # 제목에 적을 주제 수
SEARCH_HEAD = 30         # 이 안에 검색어가 들어 있어야 한다 (검사용)


def focus_from(picked: list, limit: int = FOCUS_TOPICS) -> str:
    """이 편에 실제로 많이 들어간 주제를 「인사·식당·교통」 꼴로.

    `topic` 값이 「인사·기본」·「식당·카페」처럼 두 낱말이라 그대로 이으면
    제목이 금방 넘친다. 가운뎃점 앞의 앞말만 쓴다.

    문장이 비었거나 주제가 없으면 빈 문자열이다 — 부르는 쪽이 그때는 이
    조각을 빼고 제목을 만든다. **없는 것을 지어내지 않는다.**
    """
    counts = collections.Counter(
        (item.get("topic") or "").split("·")[0].strip()
        for item in picked if item.get("topic"))
    counts.pop("", None)
    if not counts:
        return ""
    # 많이 든 것부터. 같은 수면 이름 순으로 — 같은 입력이 같은 제목을 내야
    # 한다(Counter 의 삽입 순서에 기대면 문장 순서가 제목을 바꾼다).
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return "·".join(name for name, _ in ordered[:limit])


def episode_number(published_rows, pack_id: str) -> int:
    """이 팩의 다음 회차. 기록이 없으면 1.

    `published.csv` 의 줄 수로 센다. 그 파일은 **업로드가 성공한 뒤에만**
    한 줄 늘어나므로, 실패한 빌드가 회차를 먹지 않는다.
    """
    return sum(1 for row in published_rows
               if row.get("pack") == pack_id) + 1


def published_titles(published_rows) -> set:
    return {(row.get("title") or "").strip()
            for row in published_rows if (row.get("title") or "").strip()}


def compose(template: str, *, count, minutes, topic: str = "",
            focus: str = "", episode: int = 1, taken=(),
            hook: str = "", round_label: str = "", strict: bool = False) -> str:
    """틀에 값을 넣고, 이미 낸 제목과 겹치면 회차를 붙인다.

    `{focus}` 나 `{hook}` 이 빈 값이면 그것이 든 ` | ` 조각을 통째로 버린다.
    자리만 지우면 「| 편 · 흘려듣기 35분」처럼 뜻 없는 낱말이 남는다. 틀 쪽에
    조건을 두는 것보다 여기서 치우는 편이 낫다 — packs.yaml 은 자료이고
    자료에 분기를 넣으면 읽기 어려워진다.

    `round_label` 은 주제가 도는 팩(weekly_100)이 쓴다. 주제 8개가 한 바퀴
    돌고 나면 같은 주제가 다시 오는데, 그때 " 2탄" 이 붙어 **제목이 한 번도
    겹치지 않는다.** 아래 `taken` 검사는 그것이 뚫렸을 때를 위한 두 번째 그물이다.

    `strict` 면 상한을 넘을 때 뒤 조각을 버리지 않고 **멈춘다.** weekly_100 의
    뒤 조각에는 「(한글 발음 포함)」과 회차가 들어 있어서, 버리면 지키지 못할
    약속을 지운 제목이 조용히 나가고 회차 구분도 같이 사라진다. 조각을 버리는
    쪽이 나은 팩(뒤가 길이·문장 수뿐인 것들)은 그대로 `strict=False` 다.
    """
    # 값이 빈 자리는 그것이 든 조각을 **통째로** 버린다. 자리만 지우면
    # 「| 편 · 흘려듣기 35분」이나 「100문장 | | 52분」처럼 뜻 없는 낱말과
    # 빈 칸이 남는다. 이 채널 제목은 ` | ` 로 나뉘어 있어서 조각 단위로
    # 버릴 수 있다.
    for name, value in (("focus", focus), ("hook", hook)):
        if not value:
            template = _drop_segment(template, name)
    title = _tidy(template.format(count=count, minutes=minutes, topic=topic,
                                  focus=focus, episode=episode, hook=hook,
                                  round=round_label))

    taken = {t.strip() for t in taken}
    if title in taken:
        # 겹쳤다. 회차를 붙인다 — 같은 제목을 두 번 내면 검색에서 서로를
        # 잡아먹는다.
        title = _tidy(f"{title} ({episode}회)")

    if strict and len(title) > TITLE_MAX:
        raise SystemExit(
            f"제목이 {len(title)}자다 (상한 {TITLE_MAX}). 뒤 조각을 버리면 "
            f"「(한글 발음 포함)」이나 회차가 사라지므로 자르지 않는다 — "
            f"packs.yaml 의 title 이나 hook 을 줄일 것:\n    {title}")
    return _fit(title, episode)


def _drop_segment(template: str, name: str) -> str:
    """`{name}` 이 든 ` | ` 조각을 버린다. 조각이 그것뿐이면 틀을 그대로 둔다."""
    kept = [part for part in template.split(" | ") if "{" + name + "}" not in part]
    return " | ".join(kept) or template


def _tidy(text: str) -> str:
    """focus 가 비어 생긴 빈 구두점을 치운다."""
    for _ in range(3):
        for bad, good in ((" ·  · ", " · "), ("|  · ", "| "), (" ·  |", " |"),
                          ("(  ) ", ""), ("( ) ", ""), ("  ", " ")):
            text = text.replace(bad, good)
    return text.strip(" ·|")


def _fit(title: str, episode: int) -> str:
    """상한을 넘으면 뒤 조각을 버린다. **글자를 자르지 않는다.**

    글자를 자르면 「…자면서 듣는 일본」으로 끝나 검색에도 안 걸리고 보기에도
    나쁘다. 이 채널 제목은 ` | ` 로 나뉘어 있으니 뒤 조각을 통째로 버리면
    앞의 검색어는 온전히 남는다.
    """
    if len(title) <= TITLE_MAX:
        return title
    head = title.split(" | ")[0].strip()
    if len(head) <= TITLE_MAX:
        return head
    # 앞 조각조차 넘으면 그때는 자를 수밖에 없다 — 여기까지 오면 틀이 잘못된
    # 것이므로 회차만 남겨 구분은 지킨다.
    return f"{head[:TITLE_MAX - 6].rstrip()} ({episode}회)"[:TITLE_MAX]
