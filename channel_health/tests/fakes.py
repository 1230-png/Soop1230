"""네트워크를 타지 않는 가짜 유튜브 클라이언트.

googleapiclient 는 youtube.videos().list(...).execute() 모양이다.
그 모양만 흉내 낸다.
"""


class _Call:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _Resource:
    def __init__(self, handler):
        self._handler = handler

    def list(self, **kwargs):
        return _Call(self._handler(**kwargs))


class FakeYouTube:
    """호출 인자를 기록해 두고 미리 정한 답을 돌려준다."""

    def __init__(self, channel_items=None, playlist_pages=None, video_pages=None):
        self.channel_items = channel_items if channel_items is not None else []
        self.playlist_pages = list(playlist_pages or [])
        self.video_pages = list(video_pages or [])
        self.video_calls = []

    def channels(self):
        return _Resource(lambda **_: {"items": self.channel_items})

    def playlistItems(self):  # noqa: N802 — 구글 API 이름 그대로
        def handler(**kwargs):
            token = kwargs.get("pageToken")
            index = 0 if token is None else int(token)
            return self.playlist_pages[index]
        return _Resource(handler)

    def videos(self):
        def handler(**kwargs):
            self.video_calls.append(kwargs.get("id", ""))
            return self.video_pages.pop(0)
        return _Resource(handler)


def channel_item(channel_id, uploads="UU-uploads", *, subscribers="100",
                 videos="7", views="1234"):
    """채널 항목. subscribers=None 이면 구독자를 숨긴 채널이다."""
    stats = {"videoCount": videos, "viewCount": views}
    if subscribers is not None:
        stats["subscriberCount"] = subscribers
    return {"id": channel_id,
            "contentDetails": {"relatedPlaylists": {"uploads": uploads}},
            "statistics": stats}


def playlist_page(video_ids, next_token=None):
    page = {"items": [{"contentDetails": {"videoId": vid}} for vid in video_ids]}
    if next_token is not None:
        page["nextPageToken"] = next_token
    return page


def video_item(video_id, *, views="10", duration="PT30S",
               published="2026-09-01T00:00:00Z", title="제목", likes="1",
               comments="0"):
    stats = {}
    if views is not None:
        stats["viewCount"] = views
    if likes is not None:
        stats["likeCount"] = likes
    if comments is not None:
        stats["commentCount"] = comments
    return {"id": video_id,
            "snippet": {"publishedAt": published, "title": title},
            "contentDetails": {"duration": duration},
            "statistics": stats}
