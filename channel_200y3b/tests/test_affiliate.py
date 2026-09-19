"""제휴 링크 — 고지 없이 나가지 않는가.

여기서 지키는 것은 하나다. **설명란에 제휴 링크가 있으면 대가성 고지가
반드시 함께 있고, 접히기 전 자리에 있다.** 문구가 적법한지는 사람이
확인할 몫이고 이 테스트가 보증하지 않는다.
"""

import pytest

import affiliate

LINK = "https://link.coupang.com/a/abcdef"


# --- 링크 찾기 ---------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://link.coupang.com/a/abc",
    "https://coupa.ng/xyz",              # 단축 도메인 — "coupang" 만 찾으면 놓친다
    "http://www.coupang.com/vp/products/1",
    "https://COUPA.NG/대문자",
])
def test_affiliate_links_are_recognised(url):
    assert affiliate.find_links(f"설명입니다\n{url}\n끝") == [url]


def test_an_ordinary_link_is_not_an_affiliate_link():
    text = "재생목록: https://www.youtube.com/@200-y3b/playlists"
    assert affiliate.find_links(text) == []


# --- 고지 자리 ---------------------------------------------------------

def test_the_disclosure_goes_first_because_youtube_folds_the_rest():
    built = affiliate.with_disclosure("오늘의 표현입니다.", LINK)
    assert built.splitlines()[0] == affiliate.DISCLOSURE


def test_a_disclosure_below_the_fold_does_not_count():
    """접힌 자리에 있는 고지는 표시하지 않은 것과 같다."""
    buried = "\n".join(["첫 줄", "둘째 줄", "셋째 줄", "넷째 줄",
                        affiliate.DISCLOSURE, LINK])
    assert not affiliate.has_disclosure(buried)
    with pytest.raises(affiliate.DisclosureError):
        affiliate.assert_disclosed(buried)


def test_reworded_disclosure_still_passes():
    """사람이 문장을 다듬어도 통과해야 한다."""
    text = f"※ 쿠팡 파트너스 활동으로 수수료를 받습니다.\n\n본문\n{LINK}"
    assert affiliate.has_disclosure(text)


def test_naming_coupang_without_mentioning_the_fee_is_not_a_disclosure():
    text = f"쿠팡에서 파는 교재입니다.\n{LINK}"
    assert not affiliate.has_disclosure(text)


# --- 막는가 ------------------------------------------------------------

def test_a_link_without_a_disclosure_stops_the_upload():
    """이 파일이 생긴 이유. 예전 코드는 이 모양으로 그냥 올렸다."""
    old_style = f"오늘의 표현입니다.\n\n📚 추천 상품: {LINK}"
    with pytest.raises(affiliate.DisclosureError) as caught:
        affiliate.assert_disclosed(old_style)
    assert LINK in str(caught.value)


def test_what_with_disclosure_builds_always_survives_the_check():
    built = affiliate.with_disclosure("본문", LINK)
    assert affiliate.assert_disclosed(built) == built


def test_a_description_with_no_link_is_untouched():
    assert affiliate.with_disclosure("본문입니다.", "") == "본문입니다."
    assert affiliate.assert_disclosed("본문입니다.") == "본문입니다."


def test_a_blank_link_does_not_leave_a_dangling_disclosure():
    """링크가 없는데 고지만 붙으면 안 받은 수수료를 받았다고 적는 것이다."""
    assert affiliate.DISCLOSURE not in affiliate.with_disclosure("본문", "   ")
