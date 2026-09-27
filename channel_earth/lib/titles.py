"""제목과 태그를 만든다. **구독자가 없는 채널이 발견되는 유일한 길이 검색이다.**

왜 이 파일이 따로 있는지: 제목을 `build.py` 안에서 f-string 한 줄로 만들고
있었고 그것이 이랬다 —

    지구의 오늘 — 09월 21일 지진 291건

이 문장을 검색하는 사람은 없다. 같은 저장소의 측정 기록이 그 결과를 보여
준다(2026-09-27 스냅샷). @귀트는일본어 는 롱폼 8편 중 **7편이 0회**이고
총 3회다. 구독자가 7명이라 구독 피드가 없고, 추천은 시청 신호가 있어야
시작되므로 부트스트랩이 안 되고, 검색은 제목이 검색어가 아니라서 안 걸린다.
**세 경로가 다 막히면 조회수는 0이 된다.** 0.7시간 대 3,000시간은 그래서 난
숫자다.

반대 증거도 같은 기록에 있다. @200-y3b 롱폼 12편의 중앙값은 60회인데 최대는
325회이고, 그 최대가 「영어 회화 표현 30개 몰아듣기 | 출퇴근 영어 흘려듣기
14분」이다. **"영어 흘려듣기"는 사람이 실제로 검색창에 치는 말이다.** 나머지
제목은 아니다.

그래서 규칙은 하나다. **제목의 앞부분을 사람이 검색창에 칠 말로 채운다.**
지진에서 그 말은 「지역 + 규모」다("일본 지진", "규모 6.2 지진"). 날짜와
건수는 검색어가 아니므로 뒤로 보낸다.

지역명을 한국어로 옮기는 이유도 같다. USGS 의 `place` 는 영어다
("125 km SSE of Hasaki, Japan"). 한국어 화자가 "Hasaki" 로 검색하지 않는다.
"""

from __future__ import annotations

# USGS `place` 의 마지막 쉼표 뒤(또는 문장 전체)에 나오는 지명 → 한국어.
#
# **전부 옮기지 않는다.** 한국어로 검색될 만한 곳만 넣었다 — 검색량이 없는
# 나라를 한국어로 적어 봐야 유입이 없고, 표를 크게 만들면 틀린 번역이 섞일
# 자리만 늘어난다. 표에 없으면 영어를 그대로 쓴다(그 편이 틀린 한국어보다
# 낫다). 아래 `region_ko` 가 그 규칙을 지킨다.
COUNTRY_KO = {
    "Japan": "일본",
    "South Korea": "한국",
    "North Korea": "북한",
    "Taiwan": "대만",
    "Philippines": "필리핀",
    "Indonesia": "인도네시아",
    "China": "중국",
    "Russia": "러시아",
    "Chile": "칠레",
    "Peru": "페루",
    "Mexico": "멕시코",
    "Turkey": "터키",
    "Greece": "그리스",
    "Italy": "이탈리아",
    "Iran": "이란",
    "Nepal": "네팔",
    "India": "인도",
    "New Zealand": "뉴질랜드",
    "Papua New Guinea": "파푸아뉴기니",
    "Solomon Islands": "솔로몬 제도",
    "Vanuatu": "바누아투",
    "Fiji": "피지",
    "Tonga": "통가",
    "Guatemala": "과테말라",
    "Ecuador": "에콰도르",
    "Colombia": "콜롬비아",
    "Argentina": "아르헨티나",
    "Afghanistan": "아프가니스탄",
    "Pakistan": "파키스탄",
    "Myanmar": "미얀마",
    "Alaska": "미국 알래스카",
    "Hawaii": "미국 하와이",
    "Puerto Rico": "푸에르토리코",
}

# 미국 주 약자. USGS 가 미국 안쪽은 "14 km WNW of Anza, CA" 처럼 약자로 준다.
# 여기 없는 약자는 "미국"으로만 적는다 — 주 이름을 한국어로 검색하는 사람은
# 캘리포니아 말고는 거의 없다.
US_STATE_KO = {
    "CA": "미국 캘리포니아",
    "AK": "미국 알래스카",
    "HI": "미국 하와이",
    "NV": "미국 네바다",
    "WA": "미국 워싱턴주",
    "OR": "미국 오리건",
    "OK": "미국 오클라호마",
    "UT": "미국 유타",
    "TX": "미국 텍사스",
    "MT": "미국 몬태나",
    "ID": "미국 아이다호",
    "WY": "미국 와이오밍",
    "PR": "푸에르토리코",
}

# 쉼표가 없는 바다 이름들. USGS 가 "South of the Fiji Islands" 처럼 준다.
OCEAN_KO = (
    ("Fiji", "피지 인근 해역"),
    ("Kermadec", "커머덱 제도"),
    ("Mid-Atlantic Ridge", "대서양 중앙해령"),
    ("Pacific-Antarctic Ridge", "남태평양 해령"),
    ("Southeast Indian Ridge", "인도양 해령"),
    ("Mariana", "마리아나 해구"),
    ("Kuril", "쿠릴 열도"),
    ("Molucca", "몰루카 해"),
    ("Banda Sea", "반다 해"),
    ("Scotia Sea", "스코샤 해"),
    ("Bouvet", "부베섬 인근"),
    ("Ascension", "어센션섬 인근"),
    ("Azores", "아조레스 인근"),
    ("Aleutian", "알류샨 열도"),
)

TITLE_MAX = 100   # 유튜브 제목 상한


def region_ko(place: str) -> str:
    """USGS `place` 에서 한국어 지역명을 뽑는다. 모르면 영어를 그대로 준다.

    **모르는 곳을 억지로 옮기지 않는다.** 표에 없는 지명을 음차하면 검색되지도
    않는 데다 틀린 한국어가 제목에 박힌다. 영어 그대로가 낫다.
    """
    text = (place or "").strip()
    if not text:
        return "해역"

    for needle, korean in OCEAN_KO:
        if needle.lower() in text.lower():
            return korean

    tail = text.rsplit(",", 1)[-1].strip()
    if tail in COUNTRY_KO:
        return COUNTRY_KO[tail]
    if tail in US_STATE_KO:
        return US_STATE_KO[tail]
    if len(tail) == 2 and tail.isupper():
        # 모르는 주 약자. 주를 짐작하지 않고 나라만 적는다.
        return "미국"
    if tail in ("CA", "California"):
        return "미국 캘리포니아"
    return tail or text


def headline(quake) -> str:
    """지진 한 건을 제목 앞머리로. 「지역 + 규모」 순서다.

    규모를 앞에 두지 않는 이유: 사람은 "일본 지진"을 먼저 치고 규모는 뒤에
    붙인다. 검색어의 첫 낱말이 지역인 편이 걸릴 확률이 높다.
    """
    return f"{region_ko(quake.place)} 규모 {quake.mag:.1f} 지진"


def alert_title(quake, count: int) -> str:
    """큰 지진 하나를 앞세운 제목. 이벤트 발행이 쓴다.

    이 순간이 검색 수요가 존재하는 거의 유일한 때다 — 평소 "지진" 검색량은
    낮고, 큰 것이 하나 오면 몇 시간 치솟는다. 그 몇 시간 안에 이 제목이
    걸리지 않으면 그 편은 다른 날과 똑같이 묻힌다.
    """
    when = quake.time
    base = (f"{headline(quake)} — 발생 위치와 진원 깊이 지도 "
            f"({when:%m월 %d일} UTC)")
    return _fit(base, f"{headline(quake)} — 위치와 깊이 지도")


def daily_title(quakes: list, window: str) -> str:
    """하루치 지도 제목. 가장 큰 지진을 앞에 세운다.

    건수를 앞세우지 않는다. "지진 291건"은 검색어가 아니고, 291 이라는 수가
    독자에게 뜻하는 것도 없다(미국 관측망이 촘촘해서 늘어난 수다).
    """
    if not quakes:
        return "오늘의 지진 지도"
    top = max(quakes, key=lambda q: q.mag)
    day = min(q.time for q in quakes)
    span = "이번 주" if window == "week" else "오늘"
    if top.mag >= 5.0:
        base = (f"{headline(top)} 외 — {span} 전 세계 지진 지도 "
                f"({day:%m월 %d일})")
        short = f"{headline(top)} 외 — {span} 지진 지도"
    else:
        base = (f"{span} 전 세계 지진 지도 — 가장 큰 것은 "
                f"{headline(top)} ({day:%m월 %d일})")
        short = f"{span} 전 세계 지진 지도 ({day:%m월 %d일})"
    return _fit(base, short)


def _fit(base: str, fallback: str) -> str:
    """상한을 넘으면 짧은 판으로. 잘라 내지 않는다.

    글자를 자르면 "…규모 6.2 지" 처럼 끝나서 검색에도 안 걸리고 보기에도
    나쁘다. 미리 준비한 짧은 문장으로 바꾸는 편이 낫다.
    """
    if len(base) <= TITLE_MAX:
        return base
    if len(fallback) <= TITLE_MAX:
        return fallback
    return fallback[:TITLE_MAX].rstrip()


def tags_for(quakes: list) -> list:
    """태그. 지역 태그를 섞어 준다 — 고정 태그만으로는 같은 틀이 된다."""
    base = ["지진", "실시간 지진", "지진 정보", "데이터 시각화",
            "지구과학", "USGS", "earthquake"]
    regions = []
    for q in sorted(quakes, key=lambda q: -q.mag)[:6]:
        name = region_ko(q.place)
        tag = f"{name} 지진"
        if tag not in regions and len(name) <= 12:
            regions.append(tag)
    return base + regions[:4]
