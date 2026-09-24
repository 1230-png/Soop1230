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
