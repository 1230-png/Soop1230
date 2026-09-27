"""쇼츠 발행 게이트 — 네트워크도 ffmpeg 도 타지 않는다."""

from pathlib import Path

import build
import shorts

PHRASE = {"id": "J006", "ja": "はじめまして。", "yomi": "하지메마시테",
          "ko": "처음 뵙겠습니다", "topic": "인사·기본"}


def refusal(seconds):
    meta = shorts.build_metadata(PHRASE, seconds, build.ROOT / "build" / "v.mp4")
    try:
        build.verify_publishable(meta, 1, None)
    except SystemExit as stop:
        return str(stop)
    return None


def test_a_ten_second_short_is_published():
    assert refusal(10.0) is None


def test_a_short_over_a_minute_is_stopped():
    """60초를 넘기면 쇼츠 선반에 안 뜬다."""
    assert "쇼츠" in refusal(75.0)


def test_a_near_silent_short_is_stopped():
    assert "쇼츠" in refusal(1.0)


def test_long_form_still_needs_a_minute():
    """쇼츠 예외가 롱폼의 60초 차단을 풀면 안 된다."""
    meta = {"title": "t", "description": "d", "phrase_ids": ["J001"],
            "duration_seconds": 10.0, "pack": "sleep_japanese"}
    try:
        build.verify_publishable(meta, 1, None)
    except SystemExit as stop:
        assert "10초" in str(stop)
    else:
        raise AssertionError("롱폼 10초가 통과했다")


def test_metadata_leaves_no_broken_values():
    meta = shorts.build_metadata(PHRASE, 10.0, build.ROOT / "build" / "v.mp4")
    assert "처음 뵙겠습니다" in meta["title"] and len(meta["title"]) <= 100
    assert meta["phrase_ids"] == ["J006"]
    assert Path(meta["file"]).name == "v.mp4"


# ---------------------------------------------------------------- 롱폼 연결
#
# 쇼츠는 낯선 사람에게 닿고 롱폼은 닿지 않는다. 2026-09-27 기록으로 쇼츠
# 8편은 전부 조회수가 있었고 롱폼 7편 중 6편이 0이었다. 시청 시간이 쌓이는
# 곳은 롱폼이므로, 쇼츠에서 롱폼으로 보내는 줄이 유일한 길이다.

ROWS = [
    {"published_at": "2026-09-20T07:11:23Z", "pack": "situation_pack",
     "video_id": "old_public", "privacy": "public", "title": "여행·교통"},
    {"published_at": "2026-09-25T17:05:53Z", "pack": "sleep_japanese",
     "video_id": "newest_public", "privacy": "public", "title": "수면 36분"},
    {"published_at": "2026-09-26T14:07:18Z", "pack": "shorts",
     "video_id": "a_short", "privacy": "public", "title": "쇼츠"},
]


def test_the_newest_public_long_form_is_chosen():
    assert shorts.latest_longform(ROWS)["video_id"] == "newest_public"


def test_a_short_is_never_chosen():
    """쇼츠에서 쇼츠로 보내면 시청 시간이 쌓이는 곳으로 가지 않는다."""
    only_shorts = [row for row in ROWS if row["pack"] == "shorts"]
    assert shorts.latest_longform(only_shorts) is None


def test_a_private_long_form_is_not_linked():
    """열리지 않는 링크 하나가 설명란 전체를 못 믿게 만든다."""
    private = [dict(row, privacy="private") for row in ROWS
               if row["pack"] != "shorts"]
    assert shorts.latest_longform(private) is None


def test_a_row_without_a_video_id_is_not_linked():
    broken = [dict(ROWS[0], video_id="")]
    assert shorts.latest_longform(broken) is None


def test_the_description_carries_a_real_link():
    meta = shorts.build_metadata(PHRASE, 10.0, build.ROOT / "build" / "v.mp4",
                                 latest=ROWS[1])
    assert "https://www.youtube.com/watch?v=newest_public" in meta["description"]


def test_the_description_holds_no_dead_link_when_there_is_no_long_form():
    """아직 공개 롱폼이 없을 때 'None' 이 박힌 링크가 나가면 안 된다."""
    meta = shorts.build_metadata(PHRASE, 10.0, build.ROOT / "build" / "v.mp4",
                                 latest=None)
    assert "None" not in meta["description"]
    assert "watch?v=" not in meta["description"]


def test_a_missing_published_file_is_not_an_error(tmp_path):
    """기록이 아직 없어도 쇼츠는 나가야 한다."""
    assert shorts.read_published(tmp_path / "없는파일.csv") == []
