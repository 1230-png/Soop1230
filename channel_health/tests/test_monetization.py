"""수익화 거리 — 무엇을 세고, 무엇을 세지 않고, 어디까지 말하는가.

이 모듈이 내는 시청 시간은 추정치다. 테스트의 상당수가 "추정을 사실처럼
말하지 않는가"를 본다.
"""

from datetime import datetime, timedelta, timezone

import monetization

NOW = datetime(2026, 9, 19, 3, 0, tzinfo=timezone.utc)
CHANNEL = "200y3b"


def video(*, days_ago=1, duration_s="600", views="100", video_id="v"):
    published = (NOW - timedelta(days=days_ago)).isoformat()
    return {"observed_at": "snap-1", "channel": CHANNEL, "video_id": video_id,
            "published_at": published, "duration_s": duration_s,
            "title": "제목", "views": views, "likes": "1", "comments": "0"}


def stats(subscribers="100", observed_at="snap-1"):
    return {"observed_at": observed_at, "channel": CHANNEL,
            "subscribers": subscribers, "videos": "7", "views": "1000"}


def place(videos=(), stat_rows=None):
    if stat_rows is None:
        stat_rows = [stats()]
    return monetization.standing(list(videos), list(stat_rows), CHANNEL, NOW)


# --- 시청 시간 추정 -----------------------------------------------------

def test_the_estimate_is_a_range_not_a_single_number():
    """한 값으로 내면 그 값이 사실처럼 읽힌다."""
    found = place([video(duration_s="3600", views="100")])
    assert found.hours_low < found.hours_high
    assert found.hours_high == 100 * 3600 * monetization.RETENTION_HIGH / 3600


def test_shorts_do_not_add_watch_hours():
    """숏폼 시청 시간은 파트너 프로그램이 세는 시간에 들어가지 않는다."""
    shorts_only = place([video(duration_s="45", views="100000")])
    assert shorts_only.hours_high == 0
    assert shorts_only.longform_12mo == 0


def test_longform_older_than_the_window_is_left_out():
    inside = place([video(days_ago=300, duration_s="3600")])
    outside = place([video(days_ago=400, duration_s="3600")])
    assert inside.hours_high > 0
    assert outside.hours_high == 0


def test_a_row_without_a_publish_date_is_not_counted_in_any_window():
    """날짜를 모르는 줄을 창 안에 넣으면 남은 거리가 실제보다 가깝게 나온다."""
    undated = video(duration_s="3600")
    undated["published_at"] = ""
    found = place([undated])
    assert found.hours_high == 0
    assert found.uploads_90d == 0


def test_a_row_without_a_duration_adds_no_hours():
    found = place([video(duration_s="", views="1000")])
    assert found.hours_high == 0


# --- 숏폼 조회수 창 -----------------------------------------------------

def test_shorts_views_are_counted_only_inside_ninety_days():
    fresh = place([video(days_ago=10, duration_s="45", views="500")])
    stale = place([video(days_ago=100, duration_s="45", views="500")])
    assert fresh.shorts_views_90d == 500
    assert stale.shorts_views_90d == 0


def test_recent_uploads_are_counted_for_the_three_video_requirement():
    rows = [video(days_ago=day, video_id=f"v{day}") for day in (1, 2, 3, 200)]
    assert place(rows).uploads_90d == 3


# --- 구독자 ------------------------------------------------------------

def test_the_shortfall_to_each_tier_is_reported():
    found = place([], [stats(subscribers="127")])
    assert found.subscribers_short_of(500) == 373
    assert found.subscribers_short_of(1000) == 873


def test_meeting_a_tier_leaves_no_shortfall():
    assert place([], [stats(subscribers="1500")]).subscribers_short_of(500) == 0


def test_a_hidden_subscriber_count_is_none_not_zero():
    """비공개와 0 을 섞으면 '구독자 500명 부족'을 숨긴 채널에도 적는다."""
    found = place([], [stats(subscribers="")])
    assert found.subscribers is None
    assert found.subscribers_short_of(500) is None
    assert any("비공개" in line for line in monetization.lines(found))


def test_the_newest_snapshot_wins():
    rows = [stats(subscribers="100", observed_at="snap-1"),
            stats(subscribers="300", observed_at="snap-2")]
    assert place([], rows).subscribers == 300


# --- 무엇이 더 먼가 -----------------------------------------------------

def test_the_further_gap_is_named():
    """'373명 부족'과 '2,950시간 부족'은 단위가 달라 그냥은 비교되지 않는다."""
    near_subs = place([video(duration_s="60")], [stats(subscribers="499")])
    assert any("시청 시간" in line and "더 먼 쪽" in line
               for line in monetization.lines(near_subs))


def test_nothing_is_named_when_a_tier_is_fully_met():
    plenty = [video(duration_s="3600", views="200000", video_id=f"v{n}")
              for n in range(50)]
    found = place(plenty, [stats(subscribers="5000")])
    tier = monetization.TIERS[0]
    assert monetization._nearest_gap(found, tier) is None


# --- 말하지 않는 것 -----------------------------------------------------

def test_the_lines_always_mark_the_hours_as_an_estimate():
    found = place([video(duration_s="3600")])
    assert any("추정" in line for line in monetization.lines(found))


def test_no_records_says_so_instead_of_reporting_zero():
    found = place([], [])
    assert monetization.lines(found) == ["수집된 기록이 없어 수익화 거리를 낼 수 없다."]


def test_a_shorts_only_channel_is_told_the_shorts_route_is_not_realistic():
    found = place([video(days_ago=5, duration_s="45", views="9000")])
    assert any("유일한 경로" in line for line in monetization.lines(found))


def test_uncollected_subscribers_are_not_called_hidden():
    """숨긴 것과 아직 안 읽은 것을 같은 말로 적으면 아무도 안 고친다."""
    found = place([video(duration_s="600")], [])
    assert any("아직 수집 전" in line for line in monetization.lines(found))
    assert not any("비공개" in line for line in monetization.lines(found))
