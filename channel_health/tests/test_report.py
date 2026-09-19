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
