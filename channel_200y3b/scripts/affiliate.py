"""제휴 링크와 대가성 고지를 한 곳에서 묶는다.

**링크만 들어가고 고지가 빠지는 일을 코드가 막는다.**

이 파일이 생기기 전 `upload_video.py` 는 이렇게 붙이고 있었다:

    full_description = f"{description}\\n\\n📚 추천 상품: {COUPANG_LINK}"

고지가 한 글자도 없다. `COUPANG_LINK` 가 비어 있어서 아직 나간 적은 없지만,
누군가 그 칸을 채우는 날 대가성 표시 없는 제휴 링크가 무인으로 발행된다.
링크를 넣는 경로를 `with_disclosure()` 하나로 좁히고, 그 함수가 고지를
빼먹을 수 없게 만든 것이 이 파일의 목적이다.

**고지는 맨 앞에 둔다.** 유튜브 설명란은 몇 줄 뒤부터 접히고, 숏폼에서는
거의 펼쳐지지 않는다. 접힌 자리에 있는 고지는 표시하지 않은 것과 같다.

법령 확인은 사람 몫이다. 공정거래위원회 「추천·보증 등에 관한 표시·광고
심사지침」과 쿠팡 파트너스 약관이 요구하는 문구는 바뀔 수 있고, 이 코드는
그 최신본을 확인할 수 없다. 여기 있는 것은 **"고지 없이 나가지는 않는다"는
보장**이지 "이 문구면 적법하다"는 보증이 아니다. 문구는 게시 전에
partners.coupang.com 에서 직접 확인할 것.
"""

import re

# 대가성 고지. 쿠팡 파트너스가 요구하는 문구를 기본값으로 둔다.
# 링크 생성 화면이 "반드시 기재"하라고 주는 문구를 글자 그대로 쓴다
# (2026-09-25 partners.coupang.com 에서 확인). 다듬으면 약관 위반 소지가 생긴다.
DISCLOSURE = (
    "이 포스팅은 쿠팡 파트너스 활동의 일환으로, "
    "이에 따른 일정액의 수수료를 제공받습니다."
)

# 고지가 이 줄 안에 있어야 한다. 유튜브가 설명란을 접는 지점보다 앞이다.
DISCLOSURE_WITHIN_LINES = 3

# 제휴 링크로 볼 주소. 쿠팡은 단축 도메인(coupa.ng)을 쓰기 때문에
# "coupang" 만 찾으면 놓친다.
AFFILIATE_HOSTS = ("coupa.ng", "coupang.com", "link.coupang.com")

_LINK_RE = re.compile(
    r"https?://\S*(?:" + "|".join(re.escape(host) for host in AFFILIATE_HOSTS) + r")\S*",
    re.IGNORECASE)


class DisclosureError(RuntimeError):
    """제휴 링크가 대가성 고지 없이 설명란에 들어갔다."""


def find_links(text):
    """설명란에 있는 제휴 링크 전부."""
    return _LINK_RE.findall(text or "")


def has_disclosure(text, within_lines=DISCLOSURE_WITHIN_LINES):
    """고지가 접히기 전 자리에 있는가.

    문구를 통째로 맞히지 않고 핵심 낱말로 본다. 사람이 문장을 다듬어도
    통과해야 하지만, "쿠팡"만 적고 수수료 얘기를 빼면 안 된다.
    """
    head = "\n".join((text or "").splitlines()[:within_lines])
    return "수수료" in head and ("파트너스" in head or "제휴" in head)


def assert_disclosed(text):
    """링크가 있는데 고지가 없으면 멈춘다.

    업로드 직전에 부른다. 여기서 예외를 삼키면 이 파일이 있을 이유가 없다.
    """
    links = find_links(text)
    if links and not has_disclosure(text):
        raise DisclosureError(
            f"제휴 링크 {len(links)}개가 대가성 고지 없이 설명란에 있다: "
            f"{links[0]}\n"
            f"  고지는 앞 {DISCLOSURE_WITHIN_LINES}줄 안에 있어야 한다"
            " (그 뒤는 유튜브가 접는다).\n"
            "  affiliate.with_disclosure() 로 붙일 것.")
    return text


def with_disclosure(description, link, label="추천 상품", disclosure=DISCLOSURE):
    """설명란에 제휴 링크를 붙인다. 링크가 없으면 원문 그대로.

    고지를 **맨 앞에** 놓는다. 링크 옆에 두면 접힌 자리로 들어간다.
    """
    body = (description or "").strip()
    if not (link or "").strip():
        return body
    return "\n\n".join([disclosure, body, f"📚 {label}: {link.strip()}"]).strip()
