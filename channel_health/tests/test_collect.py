"""지표 수집 — 네트워크를 타지 않는다."""

from datetime import datetime, timezone

import pytest

import channels as registry
import collect
from tests.fakes import FakeYouTube, channel_item, playlist_page, video_item

NOW = datetime(2026, 9, 19, 3, 0, tzinfo=timezone.utc)
Y3B = registry.BY_NAME["200y3b"]
ENV = {"Y3B_CLIENT_ID": "id", "Y3B_CLIENT_SECRET": "secret",
       "Y3B_REFRESH_TOKEN": "token"}


# --- 길이 읽기 ---------------------------------------------------------

@pytest.mark.parametrize("text,seconds", [
    ("PT30S", 30),
    ("PT1M30S", 90),
    ("PT12M", 720),
    ("PT1H2M3S", 3723),
    ("P1DT1H", 90000),
    ("PT0S", 0),
])
def test_durations_are_read_as_seconds(text, seconds):
    assert collect.parse_duration(text) == seconds


@pytest.mark.parametrize("text", ["", None, "30초", "PTX"])
def test_an_unreadable_duration_is_none_not_zero(text):
    """0 으로 뭉개면 보고서가 그 영상을 숏폼으로 분류한다."""
    assert collect.parse_duration(text) is None


# --- 자격 증명 ---------------------------------------------------------

def test_missing_credentials_are_named_not_guessed():
    missing = Y3B.credentials_missing({"Y3B_CLIENT_ID": "id"})
    assert missing == ["Y3B_CLIENT_SECRET", "Y3B_REFRESH_TOKEN"]


def test_blank_credentials_count_as_missing():
    """워크플로는 없는 시크릿을 빈 문자열로 넘긴다."""
    assert Y3B.credentials_missing({**ENV, "Y3B_REFRESH_TOKEN": "   "}) \
        == ["Y3B_REFRESH_TOKEN"]


def test_building_a_client_without_credentials_stops_before_the_network():
    with pytest.raises(collect.CollectError) as caught:
        collect.build_client(Y3B, {})
    assert "Y3B_CLIENT_ID" in str(caught.value)


# --- 엉뚱한 채널 -------------------------------------------------------

def test_a_token_pointing_at_another_channel_is_refused():
    """틀린 채널 숫자를 적으면 그 뒤 판단이 전부 엉뚱한 채널을 따라간다."""
    youtube = FakeYouTube(channel_items=[channel_item("UC-다른채널")])
    with pytest.raises(collect.CollectError) as caught:
        collect.uploads_playlist(youtube, Y3B, ENV)
    assert "다르다" in str(caught.value)


def test_the_expected_channel_passes():
    youtube = FakeYouTube(
        channel_items=[channel_item(Y3B.expected_channel_id, "UU-y3b")])
    assert collect.uploads_playlist(youtube, Y3B, ENV) == "UU-y3b"


def test_an_env_channel_id_overrides_the_copy_in_code():
    youtube = FakeYouTube(channel_items=[channel_item("UC-새채널", "UU-새")])
    env = {**ENV, "Y3B_CHANNEL_ID": "UC-새채널"}
    assert collect.uploads_playlist(youtube, Y3B, env) == "UU-새"


def test_a_channel_without_a_known_id_is_not_blocked():
    """MV_CHANNEL_ID 를 안 넣은 사람의 수집까지 막지는 않는다."""
    moneylogic = registry.BY_NAME["moneylogic"]
    youtube = FakeYouTube(channel_items=[channel_item("UC-아무거나", "UU-mv")])
    assert collect.uploads_playlist(youtube, moneylogic, {}) == "UU-mv"


# --- 목록 넘기기 -------------------------------------------------------

def test_every_page_of_the_uploads_playlist_is_followed():
    """한 페이지만 읽으면 오래된 영상이 통째로 빠진다."""
    youtube = FakeYouTube(playlist_pages=[
        playlist_page(["a", "b"], next_token="1"),
        playlist_page(["c"]),
    ])
    assert collect.video_ids(youtube, "UU-x") == ["a", "b", "c"]


def test_videos_are_requested_in_batches_of_fifty():
    ids = [f"v{index}" for index in range(120)]
    youtube = FakeYouTube(video_pages=[{"items": []}, {"items": []}, {"items": []}])
    collect.video_rows(youtube, ids, "200y3b", "2026-09-19T03:00:00+00:00")
    assert [len(call.split(",")) for call in youtube.video_calls] == [50, 50, 20]


# --- 줄 만들기 ---------------------------------------------------------

def test_a_row_carries_what_the_report_needs():
    youtube = FakeYouTube(video_pages=[{"items": [
        video_item("vid1", views="1234", duration="PT12M5S",
                   published="2026-09-10T00:00:00Z", title="롱폼 한 편"),
    ]}])
    row, = collect.video_rows(youtube, ["vid1"], "200y3b", "관측시각")
    assert row == {
        "observed_at": "관측시각", "channel": "200y3b", "video_id": "vid1",
        "published_at": "2026-09-10T00:00:00Z", "duration_s": 725,
        "title": "롱폼 한 편", "views": "1234", "likes": "1", "comments": "0",
    }


def test_a_disabled_counter_is_blank_not_zero():
    """좋아요를 끈 영상을 0 으로 적으면 '아무도 안 눌렀다'로 읽힌다."""
    youtube = FakeYouTube(video_pages=[{"items": [
        video_item("vid1", likes=None, comments=None),
    ]}])
    row, = collect.video_rows(youtube, ["vid1"], "200y3b", "관측시각")
    assert row["likes"] == "" and row["comments"] == ""
    assert row["views"] == "10"


def test_collect_walks_channel_then_playlist_then_videos():
    youtube = FakeYouTube(
        channel_items=[channel_item(Y3B.expected_channel_id, "UU-y3b")],
        playlist_pages=[playlist_page(["a", "b"])],
        video_pages=[{"items": [video_item("a"), video_item("b")]}],
    )
    result = collect.collect(Y3B, youtube=youtube, env=ENV, now=NOW)
    assert [row["video_id"] for row in result.videos] == ["a", "b"]
    assert all(row["observed_at"] == "2026-09-19T03:00:00+00:00"
               for row in result.videos)


def test_video_rows_and_the_subscriber_row_share_one_timestamp():
    """두 파일의 스냅샷이 어긋나면 '이때 구독자가 몇이었나'를 짝지을 수 없다."""
    youtube = FakeYouTube(
        channel_items=[channel_item(Y3B.expected_channel_id, "UU-y3b",
                                    subscribers="412")],
        playlist_pages=[playlist_page(["a"])],
        video_pages=[{"items": [video_item("a")]}],
    )
    result = collect.collect(Y3B, youtube=youtube, env=ENV, now=NOW)
    assert result.stats["observed_at"] == result.videos[0]["observed_at"]
    assert result.stats["subscribers"] == "412"
    assert result.stats["channel"] == Y3B.name


def test_a_hidden_subscriber_count_is_blank_not_zero():
    """구독자를 숨긴 채널과 구독자가 0 인 채널은 다르다."""
    youtube = FakeYouTube(
        channel_items=[channel_item(Y3B.expected_channel_id, "UU-y3b",
                                    subscribers=None)],
        playlist_pages=[playlist_page([])],
        video_pages=[],
    )
    result = collect.collect(Y3B, youtube=youtube, env=ENV, now=NOW)
    assert result.stats["subscribers"] == ""


def test_the_subscriber_row_also_refuses_another_channel():
    """영상 쪽만 막고 구독자 쪽이 뚫리면 남의 채널 구독자가 이 채널로 기록된다."""
    youtube = FakeYouTube(channel_items=[channel_item("UC-남의채널")])
    with pytest.raises(collect.CollectError):
        collect.channel_stats(youtube, Y3B, "2026-09-19T03:00:00+00:00", ENV)


def test_stats_are_written_with_their_own_header(tmp_path):
    path = tmp_path / "channel_stats.csv"
    collect.append_rows([dict.fromkeys(collect.STATS_FIELDS, "x")], path,
                        collect.STATS_FIELDS)
    header = path.read_text(encoding="utf-8").splitlines()[0]
    assert header == ",".join(collect.STATS_FIELDS)


# --- 파일 ---------------------------------------------------------------

def test_the_first_write_lays_down_a_header(tmp_path):
    path = tmp_path / "metrics.csv"
    collect.append_rows([dict.fromkeys(collect.FIELDS, "x")], path)
    assert path.read_text(encoding="utf-8").splitlines()[0] == ",".join(collect.FIELDS)


def test_later_writes_append_and_never_rewrite(tmp_path):
    """기록을 덮어쓰면 '얼마나 늘었나'가 사라진다."""
    path = tmp_path / "metrics.csv"
    collect.append_rows([dict.fromkeys(collect.FIELDS, "첫번째")], path)
    before = path.read_text(encoding="utf-8")
    collect.append_rows([dict.fromkeys(collect.FIELDS, "두번째")], path)
    after = path.read_text(encoding="utf-8")
    assert after.startswith(before)
    assert after.count("\n") == before.count("\n") + 1


def test_nothing_to_write_leaves_no_file(tmp_path):
    path = tmp_path / "metrics.csv"
    assert collect.append_rows([], path) == 0
    assert not path.exists()
