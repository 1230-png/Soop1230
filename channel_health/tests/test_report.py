"""보고서 — 무엇을 짚고 무엇을 말하지 않는가."""

from datetime import datetime, timezone

import channels as registry
import report

NOW = datetime(2026, 9, 19, 3, 0, tzinfo=timezone.utc)
Y3B = registry.BY_NAME["200y3b"]


def row(**kwargs):
    base = {"observed_at": "2026-09-19T03:00:00+00:00", "channel": "200y3b",
            "video_id": "v", "published_at": "2026-09-18T00:00:00Z",
            "duration_s": "45", "title": "제목", "views": "100",
            "likes": "1", "comments": "0"}
    base.update(kwargs)
    return base


# --- 숏폼·롱폼 가르기 --------------------------------------------------

def test_a_short_is_short_and_a_longform_is_not():
    assert report.is_short(row(duration_s="45"))
    assert not report.is_short(row(duration_s="720"))


def test_an_unknown_length_counts_as_longform():
    """숏폼으로 잘못 넣으면 롱폼 통계가 조용히 얇아진다."""
    assert not report.is_short(row(duration_s=""))


def test_the_boundary_belongs_to_shorts():
    assert report.is_short(row(duration_s=str(report.SHORT_MAX_SECONDS)))
    assert not report.is_short(row(duration_s=str(report.SHORT_MAX_SECONDS + 1)))


# --- 아무도 안 본 영상 -------------------------------------------------

def test_an_old_video_with_no_views_is_called_out():
    rows = [row(video_id="dead", views="0", title="아무도 안 본 편",
                published_at="2026-09-01T00:00:00Z")]
    found = report.channel_findings(rows, Y3B, NOW)
    assert any("조회수 0" in line and "아무도 안 본 편" in line for line in found)


def test_a_video_published_yesterday_is_not_called_dead():
    """어제 올린 것까지 실패로 세면 보고서를 믿지 않게 된다."""
    rows = [row(video_id="new", views="0",
                published_at="2026-09-18T00:00:00Z")]
    assert not any("조회수 0" in line
                   for line in report.channel_findings(rows, Y3B, NOW))


def test_a_blank_view_count_is_not_treated_as_zero():
    """지표를 못 읽은 것과 아무도 안 본 것은 다르다."""
    rows = [row(video_id="unknown", views="",
                published_at="2026-09-01T00:00:00Z")]
    assert not any("조회수 0" in line
                   for line in report.channel_findings(rows, Y3B, NOW))


# --- 요즘 낸 것 --------------------------------------------------------

def _slump(found):
    return [line for line in found if "최근" in line and "그 이전" in line]


def test_a_slump_in_recent_episodes_is_reported():
    old = [row(video_id=f"old{n}", views="1000",
               published_at=f"2026-08-{n + 1:02d}T00:00:00Z") for n in range(10)]
    recent = [row(video_id=f"new{n}", views="10",
                  published_at=f"2026-09-1{n}T00:00:00Z") for n in range(5)]
    assert _slump(report.channel_findings(old + recent, Y3B, NOW))


def test_steady_numbers_do_not_raise_a_slump():
    rows = [row(video_id=f"v{n}", views="100",
                published_at=f"2026-09-{n + 1:02d}T00:00:00Z") for n in range(10)]
    assert not _slump(report.channel_findings(rows, Y3B, NOW))


def test_the_baseline_excludes_the_recent_episodes_it_is_judging():
    """겹쳐 놓으면 영상이 적은 채널에서 최근 편이 기준을 자기 쪽으로 끌어내린다.

    7편 중 뒤의 4편이 부진한 실제 모양. 전체 중앙값과 견주면 기준이 12 로
    내려앉아 검사가 조용히 지나간다.
    """
    strong = [row(video_id=f"s{n}", views="300",
                  published_at=f"2026-09-0{n + 1}T00:00:00Z") for n in range(3)]
    weak = [row(video_id=f"w{n}", views="12",
                published_at=f"2026-09-1{n}T00:00:00Z") for n in range(4)]
    assert _slump(report.channel_findings(strong + weak, Y3B, NOW))


def test_a_slump_needs_enough_earlier_episodes_to_compare_against():
    """두어 편으로 낸 중앙값은 한 편만 튀어도 뒤집힌다."""
    rows = [row(video_id="old", views="1000",
                published_at="2026-08-01T00:00:00Z")]
    rows += [row(video_id=f"new{n}", views="10",
                 published_at=f"2026-09-1{n}T00:00:00Z") for n in range(5)]
    assert not _slump(report.channel_findings(rows, Y3B, NOW))


# --- 롱폼이 막혔나 -----------------------------------------------------

def test_longform_lagging_far_behind_shorts_is_called_out():
    """시청 시간을 쌓는 자리는 롱폼뿐이다. 여기가 막히면 숏폼은 소용없다."""
    shorts = [row(video_id=f"s{n}", views="400", duration_s="45",
                  published_at=f"2026-09-{n + 1:02d}T00:00:00Z") for n in range(6)]
    longs = [row(video_id=f"L{n}", views="20", duration_s="1800",
                 published_at=f"2026-09-{n + 1:02d}T00:00:00Z") for n in range(3)]
    found = report.channel_findings(shorts + longs, Y3B, NOW)
    assert any("롱폼 중앙값" in line for line in found)


def test_a_single_longform_is_not_enough_to_judge():
    shorts = [row(video_id=f"s{n}", views="400", duration_s="45",
                  published_at=f"2026-09-{n + 1:02d}T00:00:00Z") for n in range(6)]
    longs = [row(video_id="L0", views="1", duration_s="1800",
                 published_at="2026-09-02T00:00:00Z")]
    assert not any("롱폼 중앙값" in line
                   for line in report.channel_findings(shorts + longs, Y3B, NOW))


def test_a_channel_with_no_shorts_raises_no_longform_comparison():
    longs = [row(video_id=f"L{n}", views="20", duration_s="1800",
                 published_at=f"2026-09-{n + 1:02d}T00:00:00Z") for n in range(3)]
    assert not any("롱폼 중앙값" in line
                   for line in report.channel_findings(longs, Y3B, NOW))


# --- 발행이 끊겼나 -----------------------------------------------------

def test_a_stalled_pipeline_is_reported():
    rows = [row(published_at="2026-09-10T00:00:00Z")]
    found = report.channel_findings(rows, Y3B, NOW)
    assert any("마지막 발행이 9일 전" in line for line in found)


def test_publishing_today_is_not_a_stall():
    rows = [row(published_at="2026-09-19T00:00:00Z")]
    assert not any("마지막 발행이" in line
                   for line in report.channel_findings(rows, Y3B, NOW))


# --- 증감 ---------------------------------------------------------------

def test_growth_needs_two_snapshots():
    rows = [row()]
    found = report.channel_findings(rows, Y3B, NOW)
    assert any("스냅샷이 하나뿐" in line for line in found)
    assert not any("합계" in line for line in found)


def test_growth_is_measured_against_the_previous_snapshot():
    rows = [
        row(observed_at="2026-09-12T03:00:00+00:00", video_id="v", views="100"),
        row(observed_at="2026-09-19T03:00:00+00:00", video_id="v", views="175"),
    ]
    found = report.channel_findings(rows, Y3B, NOW)
    assert any("+75" in line for line in found)


def test_an_empty_log_says_so_instead_of_pretending():
    found = report.channel_findings([], Y3B, NOW)
    assert found == ["기록이 없다. 아직 한 번도 수집되지 않았다."]


# --- 섞어 읽지 않게 ----------------------------------------------------

def test_the_report_states_that_views_are_not_watch_time():
    """숏폼 조회수가 올랐다고 수익화가 가까워졌다고 읽으면 정확히 반대다."""
    text = report.build([row()], NOW)
    assert "시청 시간이 아니다" in text
    assert "3,000시간" in text


def test_every_channel_gets_a_section_even_with_no_data():
    text = report.build([], NOW)
    for channel in registry.CHANNELS:
        assert channel.label in text


class TestGrowthSplit:
    """증가분을 「기존 영상이 번 것」과 「새 영상이 번 것」으로 나누는 부분.

    이 검사가 있는 이유는 실측이다. 2026-09-19→27 사이 @200-y3b 는 조회수가
    22,276 늘었는데 기존 82편이 번 것은 1,108(5.0%)뿐이었다. 합계만 보는
    보고서는 그 주를 「조회수 2만 증가」로 적었을 것이고, 그것은 **발행을
    멈추면 0 이 되는 구조를 감추는 문장**이다.
    """

    def test_기존_영상과_신규_영상을_나눈다(self):
        before = [{"video_id": "a", "views": "100"},
                  {"video_id": "b", "views": "50"}]
        after = [{"video_id": "a", "views": "130"},
                 {"video_id": "b", "views": "52"},
                 {"video_id": "c", "views": "900"}]
        carried, fresh, count = report._split_growth(before, after)
        assert (carried, fresh, count) == (32, 900, 2)

    def test_줄어든_것도_센다(self):
        # 조회수가 줄어드는 일은 드물지만(스팸 정리 등) 있다. 양수로
        # 접으면 기존 영상이 실제보다 잘 버티는 것처럼 보인다.
        carried, fresh, count = report._split_growth(
            [{"video_id": "a", "views": "100"}],
            [{"video_id": "a", "views": "90"}])
        assert carried == -10 and fresh == 0 and count == 1

    def test_id_없는_줄은_건너뛴다(self):
        carried, fresh, _ = report._split_growth(
            [{"views": "10"}], [{"views": "20"}, {"video_id": "x", "views": "5"}])
        assert carried == 0 and fresh == 25

    def test_빈_스냅샷(self):
        assert report._split_growth([], []) == (0, 0, 0)

    def test_기존_비중이_낮으면_짚는다(self):
        found = report._carry_findings(carried=1108, fresh=21168,
                                      carried_count=82, days=7)
        assert found and "5.0%" in found[0]
        assert "0 에 수렴" in found[0]

    def test_기존_비중이_충분하면_조용하다(self):
        # 자산이 쌓이고 있으면 이 줄은 나오지 않아야 한다. 매주 뜨는
        # 경고는 안 읽힌다.
        assert report._carry_findings(carried=800, fresh=1000,
                                     carried_count=30, days=7) == []

    def test_영상이_적으면_비율을_말하지_않는다(self):
        # 세 편으로 비율을 내면 한 편 터진 것만으로 뒤집힌다.
        assert report._carry_findings(carried=1, fresh=999,
                                      carried_count=3, days=7) == []

    def test_증가가_없으면_말하지_않는다(self):
        assert report._carry_findings(carried=0, fresh=0,
                                      carried_count=50, days=7) == []

    def test_보고서_본문에_기존과_신규가_같이_적힌다(self):
        rows = []
        for stamp, bump in (("2026-09-01T00:00:00+00:00", 0),
                            ("2026-09-08T00:00:00+00:00", 1)):
            for index in range(10):
                rows.append({
                    "observed_at": stamp, "channel": "200y3b",
                    "video_id": f"old{index}", "duration_s": "600",
                    "published_at": "2026-08-01T00:00:00Z",
                    "title": f"예전 {index}", "views": str(100 + bump),
                    "likes": "0", "comments": "0"})
            if bump:
                rows.append({
                    "observed_at": stamp, "channel": "200y3b",
                    "video_id": "new1", "duration_s": "600",
                    "published_at": "2026-09-07T00:00:00Z",
                    "title": "새것", "views": "5000",
                    "likes": "0", "comments": "0"})
        text = report.build(rows, now=datetime(2026, 9, 8, tzinfo=timezone.utc))
        assert "기존 10편이 번 것 +10" in text
        assert "새로 올린 것 +5000" in text
        assert "증가분의 0.2%만 기존 영상에서 왔다" in text


class TestExperiments:
    """바꾼 것이 먹혔는지 읽는 부분.

    **여기 없으면 재시험이 되지 않는다** — 몇 주 뒤에 조회수를 봐도 그것이
    바꾼 것 때문인지 알 방법이 없다. jp 롱폼 제목을 2026-09-27 에 검색어형으로
    바꿨고, 그 판단이 맞았는지는 이 줄이 말해 준다.
    """

    def long_row(self, day, views, channel="jp"):
        return {"observed_at": "2026-10-11T00:00:00+00:00", "channel": channel,
                "video_id": f"v{day}{views}", "duration_s": "1200",
                "published_at": f"2026-{day}T00:00:00Z", "title": "제목",
                "views": str(views), "likes": "0", "comments": "0"}

    def test_표본이_모이기_전에는_결론을_내지_않는다(self):
        # 한두 편으로 중앙값을 내면 그 한 편이 전부를 말하게 된다.
        latest = [self.long_row("09-20", 0), self.long_row("09-29", 40)]
        found = report._experiment_findings(
            latest, "jp", datetime(2026, 9, 30, tzinfo=timezone.utc))
        assert len(found) == 1
        assert "아직 결론을 내지 말 것" in found[0]
        assert "바꾼 뒤 롱폼 1편" in found[0]

    def test_올랐으면_올랐다고_적는다(self):
        latest = [self.long_row("09-20", 0), self.long_row("09-21", 0),
                  self.long_row("09-29", 30), self.long_row("09-30", 50),
                  self.long_row("10-01", 40)]
        found = report._experiment_findings(
            latest, "jp", datetime(2026, 10, 11, tzinfo=timezone.utc))
        assert "올랐다" in found[0] and "바꾼 뒤 3편 중앙값 40" in found[0]

    def test_내렸으면_형식을_다시_보라고_적는다(self):
        # 제목을 고쳐도 안 되면 다음에 볼 것은 제목이 아니다.
        latest = [self.long_row("09-20", 100), self.long_row("09-21", 100),
                  self.long_row("09-29", 1), self.long_row("09-30", 2),
                  self.long_row("10-01", 0)]
        found = report._experiment_findings(
            latest, "jp", datetime(2026, 10, 11, tzinfo=timezone.utc))
        assert "내렸다" in found[0] and "형식 자체를 다시 볼 것" in found[0]

    def test_숏폼은_세지_않는다(self):
        # Shorts 피드가 따로 배급해서 제목 영향이 다르고, 시청 시간에도
        # 들어가지 않는다.
        latest = [self.long_row("09-20", 0)]
        for index in range(5):
            latest.append({"observed_at": "2026-10-11T00:00:00+00:00",
                           "channel": "jp", "video_id": f"s{index}",
                           "duration_s": "10",
                           "published_at": "2026-09-30T00:00:00Z",
                           "title": "쇼츠", "views": "500",
                           "likes": "0", "comments": "0"})
        found = report._experiment_findings(
            latest, "jp", datetime(2026, 10, 11, tzinfo=timezone.utc))
        assert "바꾼 뒤 롱폼 0편" in found[0]

    def test_실험이_없는_채널은_조용하다(self):
        assert report._experiment_findings(
            [self.long_row("09-20", 5, channel="200y3b")], "200y3b",
            datetime(2026, 10, 11, tzinfo=timezone.utc)) == []

    def test_보고서_본문에_들어간다(self):
        rows = [self.long_row("09-20", 0), self.long_row("09-29", 10)]
        text = report.build(rows, now=datetime(2026, 10, 4, tzinfo=timezone.utc))
        assert "재시험" in text and "제목을 검색어형으로" in text
