"""제목이 검색어가 되는지 검사한다.

이 검사가 있는 이유는 `lib/titles.py` 머리에 적어 뒀다 — 같은 저장소의
측정 기록에서 롱폼 8편 중 7편이 0회였고, 그 채널과 유일하게 다른 점이
제목이었다. 제목은 **공개 뒤에 고쳐도 검색 순위가 돌아오지 않으므로**
발행 전에 코드로 막는 편이 낫다.
"""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import titles
from lib.sources import Quake


def quake(mag, place, hour=3, lat=0.0, lon=0.0, depth=10.0, qid="q"):
    return Quake(id=qid, time=dt.datetime(2026, 9, 27, hour, 12,
                                          tzinfo=dt.timezone.utc),
                 lat=lat, lon=lon, depth_km=depth, mag=mag, place=place)


class TestRegionKo:
    def test_나라_이름을_한국어로(self):
        assert titles.region_ko("125 km SSE of Hasaki, Japan") == "일본"
        assert titles.region_ko("97 km SW of Kirakira, Solomon Islands") == "솔로몬 제도"

    def test_미국_주_약자(self):
        assert titles.region_ko("14 km WNW of Anza, CA") == "미국 캘리포니아"
        assert titles.region_ko("3 km N of Somewhere, OK") == "미국 오클라호마"

    def test_모르는_주_약자는_나라만(self):
        # 주 이름을 짐작해서 적으면 틀린 한국어가 제목에 박힌다.
        assert titles.region_ko("3 km N of Somewhere, ZZ") == "미국"

    def test_쉼표_없는_해역(self):
        assert titles.region_ko("South of the Fiji Islands") == "피지 인근 해역"
        assert titles.region_ko("northern Mid-Atlantic Ridge") == "대서양 중앙해령"

    def test_모르는_지명은_영어_그대로(self):
        # 음차하면 검색도 안 되고 틀릴 위험만 있다. 영어가 낫다.
        assert titles.region_ko("5 km N of Nowhere, Freedonia") == "Freedonia"

    def test_빈_값에서_죽지_않는다(self):
        assert titles.region_ko("") == "해역"
        assert titles.region_ko(None) == "해역"


class TestTitle:
    def test_지역이_제목_맨_앞에_온다(self):
        # 사람은 "일본 지진"을 먼저 친다. 첫 낱말이 지역이어야 걸린다.
        title = titles.alert_title(quake(6.4, "125 km SSE of Hasaki, Japan"), 200)
        assert title.startswith("일본 규모 6.4 지진")

    def test_날짜와_건수가_앞에_오지_않는다(self):
        title = titles.daily_title([quake(6.1, "125 km SSE of Hasaki, Japan")], "day")
        assert not title.startswith("지구의 오늘")
        assert "291건" not in title
        assert title.index("일본") < title.index("09월")

    def test_가장_큰_지진을_앞세운다(self):
        qs = [quake(3.1, "14 km WNW of Anza, CA", qid="a"),
              quake(6.2, "125 km SSE of Hasaki, Japan", qid="b")]
        assert titles.daily_title(qs, "day").startswith("일본 규모 6.2")

    def test_조용한_날은_지도가_주어다(self):
        # M5 미만뿐이면 그 지진을 앞세울 값이 없다 — 검색되는 말이 아니다.
        title = titles.daily_title([quake(4.2, "14 km WNW of Anza, CA")], "day")
        assert title.startswith("오늘 전 세계 지진 지도")

    def test_주간은_이번_주로_적는다(self):
        title = titles.daily_title([quake(6.6, "South of the Fiji Islands")], "week")
        assert "이번 주" in title and "오늘" not in title

    def test_빈_목록에서_죽지_않는다(self):
        assert titles.daily_title([], "day")

    def test_상한을_넘으면_짧은_판으로_바꾼다(self):
        # 글자를 자르면 "…규모 6.2 지" 로 끝나 검색에도 안 걸린다.
        long_place = "125 km SSE of " + ("아주긴지명" * 20) + ", Japan"
        for title in (titles.alert_title(quake(6.4, long_place), 9),
                      titles.daily_title([quake(6.4, long_place)], "day")):
            assert len(title) <= titles.TITLE_MAX

    def test_모든_제목이_상한_안에(self):
        for place in ("125 km SSE of Hasaki, Japan", "South of the Fiji Islands",
                      "97 km SW of Kirakira, Solomon Islands",
                      "14 km WNW of Anza, CA", ""):
            for mag in (4.2, 5.0, 6.9, 7.8):
                q = quake(mag, place)
                assert 0 < len(titles.alert_title(q, 5)) <= titles.TITLE_MAX
                assert 0 < len(titles.daily_title([q], "day")) <= titles.TITLE_MAX


class TestTags:
    def test_지역_태그가_섞인다(self):
        # 고정 태그만 쓰면 매 편이 같은 틀이 된다.
        tags = titles.tags_for([quake(6.1, "125 km SSE of Hasaki, Japan")])
        assert "일본 지진" in tags and "지진" in tags

    def test_지역_태그가_중복되지_않는다(self):
        qs = [quake(6.1, "1 km N of A, Japan", qid="a"),
              quake(6.0, "2 km N of B, Japan", qid="b")]
        assert titles.tags_for(qs).count("일본 지진") == 1

    def test_빈_목록에서_죽지_않는다(self):
        assert "지진" in titles.tags_for([])
