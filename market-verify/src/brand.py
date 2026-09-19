"""채널 정체성. 이름·소개·면책 문구를 여기서만 고친다.

여러 곳에 흩어 두면 채널 이름을 바꿀 때 한 군데를 빠뜨린다.
"""

import re

NAME = "머니로직"
NAME_EN = "MoneyLogic"

# 유튜브 '정보' 탭에 적은 소개문과 같은 내용을 유지한다.
ABOUT = (
    "복잡한 금융 시장의 흐름과 암호화폐의 기술적 본질을 데이터와 구조로 해부합니다. "
    "감정에 휘둘리는 투자가 아닌, 철저한 로직과 수치를 기반으로 "
    "자산의 가치와 시장의 원리를 분석합니다."
)

# 채널이 다루는 세 갈래.
# market-verify 가 지금 만드는 것은 세 번째 갈래의 일부(조건-이후 분포)뿐이다.
PILLARS = [
    "가상자산 네트워크 기술 및 토크노믹스 해부",
    "매크로 경제 지표와 유동성 데이터 분석",
    "수학적 투자 전략(분할 매수, 리밸런싱 등)의 메커니즘 검증",
]

# 채널 표준 면책 문구. 국내 유사투자자문 규제 때문에 매 영상에 붙인다.
# 대본의 설명란 마지막 줄과 문구가 겹쳐도 이쪽을 그대로 유지한다.
# 채널 전체에 걸린 약속이라 영상마다 같은 문장으로 나가야 한다.
DISCLAIMER = (
    "본 채널의 모든 콘텐츠는 정보 제공 및 교육 목적의 데이터 분석 영상이며, "
    "특정 자산의 매수·매도를 추천하거나 권유하지 않습니다. "
    "모든 투자의 판단과 책임은 투자자 본인에게 있습니다."
)

TAGS = [
    "머니로직",
    "MoneyLogic",
    "데이터분석",
    "투자전략검증",
    "매크로",
    "토크노믹스",
    "백테스트",
]


# 이 채널은 제휴 링크를 쓰지 않는다.
#
# 다른 채널(@200-y3b)에는 쿠팡 파트너스 자리를 뒀지만 여기는 다르다. 바로 위
# DISCLAIMER 가 "추천하거나 권유하지 않습니다"라고 약속하는데, 수수료를 받는
# 상품 링크는 그 자체로 대가를 받은 추천이다. 한 화면에 같이 두면 시청자가
# 보는 것은 면책이 아니라 모순이고, 이 채널이 파는 것은 그 신뢰뿐이다.
#
# 금융 주제는 광고 단가가 높은 편으로 알려져 있어, 제휴 수수료 때문에 정식
# 파트너 쪽을 위험에 빠뜨리는 것은 큰 것을 작은 것과 바꾸는 거래다.
# `validator.py` 가 대본을 판정하듯 여기서도 코드가 판정한다 — 급할 때
# 사람이 한 번만 눈감으면 무인으로 나간다.
AFFILIATE_HOSTS = ("coupa.ng", "coupang.com", "aliexpress", "amzn.to")

_AFFILIATE_RE = re.compile(
    r"https?://\S*(?:" + "|".join(re.escape(h) for h in AFFILIATE_HOSTS) + r")\S*",
    re.IGNORECASE)


class AffiliateLinkError(RuntimeError):
    """제휴 링크가 머니로직 설명란에 들어갔다."""


def video_description(script_description):
    """대본의 설명란 뒤에 채널 표준 문구를 붙인다.

    제휴 링크가 섞여 있으면 올리지 않고 멈춘다.
    """
    parts = [script_description.strip(), DISCLAIMER]
    text = "\n\n".join(part for part in parts if part)
    found = _AFFILIATE_RE.findall(text)
    if found:
        raise AffiliateLinkError(
            f"머니로직 설명란에 제휴 링크가 있다: {found[0]}\n"
            "  이 채널은 제휴 링크를 쓰지 않는다 — 면책 문구와 정면으로 어긋난다.\n"
            "  이유는 brand.py 의 주석에 적어 뒀다.")
    return text
