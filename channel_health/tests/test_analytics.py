"""시청 지속률 — 네트워크를 타지 않는다.

이 숫자가 필요한 이유는 하나다. 조회수로는 **어느 형식이 사람을 붙잡는지**
알 수 없다. 수면 팩과 상황별 팩 중 뭐가 나은지 물어도, 지금까지는 답할
자료가 없었다. 지속률이 그 답이다.
"""

import analytics


class FakeAnalytics:
    """youtubeAnalytics 는 reports().query(...).execute() 모양이다."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def reports(self):
        return self

    def query(self, **kwargs):
        self.calls.append(kwargs)
        return self

    def execute(self):
        if not self._responses:
            raise AssertionError("예상보다 많이 불렀다")
        return self._responses.pop(0)


def response(rows, names=("video", "views", "estimatedMinutesWatched",
                          "averageViewDuration", "averageViewPercentage")):
    return {"columnHeaders": [{"name": n} for n in names], "rows": rows}


# --- 읽어 온 것을 줄로 --------------------------------------------------

def test_a_video_row_carries_what_a_format_comparison_needs():
    got = analytics.video_rows(
        response([["vid1", 120, 400, 200, 35.5]]), "jp", "관측시각", days=90)
    assert got == [{
        "observed_at": "관측시각", "channel": "jp", "scope": "video",
        "video_id": "vid1", "days": "90", "views": "120",
        "minutes_watched": "400", "avg_view_seconds": "200",
        "avg_view_percent": "35.5",
    }]


def test_columns_are_read_by_name_not_position():
    """유튜브가 칸 순서를 바꿔도 값이 어긋나면 안 된다.

    channel_200y3b 에서 0번 칸을 집었다가 phrase_id 가 아니라 date 를 모은
    적이 있다. 같은 실수를 API 응답에서 반복하지 않는다.
    """
    got = analytics.video_rows(
        response([[35.5, 400, "vid1", 200, 120]],
                 names=("averageViewPercentage", "estimatedMinutesWatched",
                        "video", "averageViewDuration", "views")),
        "jp", "관측시각", days=90)
    assert got[0]["video_id"] == "vid1"
    assert got[0]["views"] == "120"
    assert got[0]["avg_view_percent"] == "35.5"


def test_no_rows_is_not_an_error():
    """올린 지 얼마 안 된 채널은 돌려줄 것이 없다. 빈 것은 실패가 아니다."""
    assert analytics.video_rows({"columnHeaders": []}, "jp", "t", days=90) == []


def test_a_missing_column_is_blank_not_zero():
    """0 은 '아무도 안 봤다'는 뜻이다. 모르는 것과 다르다."""
    got = analytics.video_rows(
        response([["vid1", 120]], names=("video", "views")),
        "jp", "t", days=90)
    assert got[0]["minutes_watched"] == ""
    assert got[0]["views"] == "120"


def test_the_channel_row_has_no_video_id():
    got = analytics.channel_row(
        response([[5000]], names=("estimatedMinutesWatched",)),
        "jp", "관측시각", days=365)
    assert got["scope"] == "channel"
    assert got["video_id"] == ""
    assert got["minutes_watched"] == "5000"
    assert got["days"] == "365"


# --- 묻는 방식 -----------------------------------------------------------

def test_videos_are_asked_for_in_chunks():
    """필터에 넣을 수 있는 영상 수에 한도가 있다. 한 번에 다 넣지 않는다."""
    ids = [f"v{i}" for i in range(analytics.CHUNK + 5)]
    fake = FakeAnalytics([response([]), response([])])
    analytics.fetch_video_retention(fake, ids, "2026-06-22", "2026-09-20")
    assert len(fake.calls) == 2
    first = fake.calls[0]["filters"].split("==")[1].split(",")
    assert len(first) == analytics.CHUNK


def test_the_query_asks_only_for_this_channel():
    fake = FakeAnalytics([response([])])
    analytics.fetch_video_retention(fake, ["v1"], "2026-06-22", "2026-09-20")
    assert fake.calls[0]["ids"] == "channel==MINE"


def test_no_videos_means_no_call_at_all():
    fake = FakeAnalytics([])
    assert analytics.fetch_video_retention(fake, [], "a", "b") == []


# --- 권한이 없을 때 -------------------------------------------------------

def test_a_token_without_the_scope_says_so_plainly():
    """200y3b 토큰에는 이 권한이 없다. 여기서 뭉개면 왜 비었는지 모른다."""
    assert "yt-analytics.readonly" in analytics.SCOPE_HINT


# --- 날짜 창 -------------------------------------------------------------

def test_the_window_is_inclusive_of_today():
    from datetime import date
    start, end = analytics.window(date(2026, 9, 20), days=90)
    assert end == "2026-09-20"
    # 오늘을 포함해서 90일이다 — 89일 전이 시작이지 90일 전이 아니다.
    assert start == "2026-06-23"
    assert (date.fromisoformat(end) - date.fromisoformat(start)).days == 89


# --- 수집에 이어 붙였을 때 -------------------------------------------------

def test_a_channel_without_the_scope_does_not_stop_the_others(capsys):
    """@200-y3b 토큰에는 이 권한이 없다. 그 채널 때문에 일요일 수집 전체가
    죽으면, 읽을 수 있었던 채널의 스냅샷까지 같이 잃는다.
    """
    import collect

    def boom(channel, env=None):
        raise analytics.AnalyticsError(analytics.SCOPE_HINT)

    rows = collect.retention_rows_for(
        object(), "관측시각", client=boom, rows_for=None)
    assert rows == []
    assert "yt-analytics.readonly" in capsys.readouterr().err


def test_rows_come_back_when_the_scope_is_there():
    import collect

    class Channel:
        name = "jp"
        label = "@귀트는일본어"

    sentinel = [{"video_id": "v1"}]
    rows = collect.retention_rows_for(
        Channel(), "관측시각",
        client=lambda channel, env=None: "클라이언트",
        rows_for=lambda ch, cl, ids, at: sentinel,
        video_ids=["v1"])
    assert rows is sentinel
