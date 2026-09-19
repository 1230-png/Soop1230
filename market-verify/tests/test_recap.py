"""몰아보기 — 구간 선택과 소재 복원.

네트워크를 타지 않는다. 블록을 다시 뽑는 부분은 도구를 가짜로 바꿔 넣는다.
"""

from datetime import datetime, timezone

import pytest

from src import news_topics, recap, run_recap, topics

KST = recap.KST


def _log(tmp_path, rows):
    """(시각 ISO, key, tool) 목록을 used_topics.csv 모양으로 쓴다."""
    path = tmp_path / "used_topics.csv"
    lines = ["date,key,tool,label"]
    lines += [f"{when},{key},{tool},{key} 라벨" for when, key, tool in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --- 구간 -------------------------------------------------------------

def test_week_starts_on_monday_in_korean_time():
    """발행이 한국 아침이라 UTC 로 자르면 월요일 회차가 지난주로 밀린다."""
    friday = datetime(2026, 9, 18, 3, 0, tzinfo=timezone.utc)  # KST 금 12:00
    start, _ = recap.window_bounds(recap.WEEK, friday)
    assert start.strftime("%Y-%m-%d %H:%M") == "2026-09-14 00:00"
    assert start.tzinfo == KST


def test_month_starts_on_the_first():
    start, _ = recap.window_bounds(recap.MONTH, datetime(2026, 9, 18, 3, tzinfo=timezone.utc))
    assert start.strftime("%Y-%m-%d") == "2026-09-01"


def test_a_monday_dawn_utc_episode_lands_in_the_new_week():
    """한국 월요일 09:05 은 UTC 로 일요일 00:05 이다. 지난주로 새면 안 된다."""
    monday_kst = datetime(2026, 9, 21, 0, 5, tzinfo=timezone.utc)  # KST 월 09:05
    start, _ = recap.window_bounds(recap.WEEK, monday_kst)
    assert start.strftime("%Y-%m-%d") == "2026-09-21"


def test_window_key_is_unique_per_window():
    week = datetime(2026, 9, 18, 3, tzinfo=timezone.utc)
    assert recap.window_key(recap.WEEK, week) == "recap-week-2026-W38"
    assert recap.window_key(recap.MONTH, week) == "recap-month-2026-09"


def test_unknown_window_is_refused():
    with pytest.raises(ValueError):
        recap.window_bounds("quarter")


# --- 어떤 회차를 묶나 -------------------------------------------------

def test_only_episodes_inside_the_window_are_collected(tmp_path):
    now = datetime(2026, 9, 18, 3, tzinfo=timezone.utc)
    path = _log(tmp_path, [
        ("2026-09-11T00:05:00+00:00", "gspc-down3", "run"),        # 지난주
        ("2026-09-15T00:05:00+00:00", "gspc-drawdown20", "run"),   # 이번주
        ("2026-09-17T00:05:00+00:00", "vix-threshold30", "run"),   # 이번주
    ])
    keys = [row["key"] for row in recap.episodes_in_window(recap.WEEK, path, now)]
    assert keys == ["gspc-drawdown20", "vix-threshold30"]


def test_a_recap_is_not_folded_into_the_next_recap(tmp_path):
    """묶은 것을 또 묶으면 같은 영상이 겹겹이 쌓인다."""
    now = datetime(2026, 9, 18, 3, tzinfo=timezone.utc)
    path = _log(tmp_path, [
        ("2026-09-15T00:05:00+00:00", "gspc-down3", "run"),
        ("2026-09-16T00:05:00+00:00", "recap-week-2026-W37", recap.RECAP_TOOL),
    ])
    keys = [row["key"] for row in recap.episodes_in_window(recap.WEEK, path, now)]
    assert keys == ["gspc-down3"]


def test_a_broken_timestamp_does_not_lose_the_whole_window(tmp_path):
    """줄 하나가 깨졌다고 그 주 몰아보기를 포기하지 않는다."""
    now = datetime(2026, 9, 18, 3, tzinfo=timezone.utc)
    path = _log(tmp_path, [
        ("어제", "gspc-down3", "run"),
        ("2026-09-15T00:05:00+00:00", "gspc-drawdown20", "run"),
    ])
    keys = [row["key"] for row in recap.episodes_in_window(recap.WEEK, path, now)]
    assert keys == ["gspc-drawdown20"]


def test_missing_log_is_not_an_error(tmp_path):
    assert recap.episodes_in_window(recap.WEEK, tmp_path / "없다.csv") == []


# --- 소재 복원 --------------------------------------------------------

def test_pool_keys_resolve_through_the_pool():
    topic = recap.resolve({"key": "btc-dilution"})
    assert topic is not None
    assert topic.tool == "run_tokenomics"


@pytest.mark.parametrize("key,ticker,condition", [
    ("news-ETH-USD-down3", "ETH-USD", "down-weeks"),
    ("news-BTC-USD-drawdown30", "BTC-USD", "drawdown"),
    ("news-^IXIC-down3", "^IXIC", "down-weeks"),
    ("news-^GSPC-drawdown20", "^GSPC", "drawdown"),
    ("news-vix-30", "^VIX", "threshold"),
])
def test_news_keys_resolve_back_to_their_tool_arguments(key, ticker, condition):
    """로그에는 key 만 남는다. 도구 인자를 여기서 다시 세운다."""
    topic = news_topics.topic_from_key(key)
    assert topic is not None
    argv = topic.argv
    assert argv[argv.index("--ticker") + 1] == ticker
    assert argv[argv.index("--condition") + 1] == condition


def test_a_hyphenated_ticker_is_not_split_at_the_hyphen():
    """'ETH-USD' 를 '-' 로 자르면 'ETH' 가 된다. 후보를 만들어 맞추는 이유다."""
    topic = news_topics.topic_from_key("news-ETH-USD-down3")
    assert topic.argv[topic.argv.index("--ticker") + 1] == "ETH-USD"


def test_an_unknown_key_returns_none_instead_of_guessing():
    assert news_topics.topic_from_key("news-DOGE-USD-down3") is None
    assert news_topics.topic_from_key("뭔가-이상한-키") is None
    assert recap.resolve({"key": "없는키"}) is None


def test_unresolved_keys_are_reported_not_silently_dropped():
    said = []
    found = recap.resolve_all(
        [{"key": "gspc-down3"}, {"key": "없는키"}], log=said.append
    )
    assert [t.key for t in found] == ["gspc-down3"]
    assert any("없는키" in line for line in said)


# --- 블록 묶기 --------------------------------------------------------

def test_combined_block_labels_each_condition():
    """이어 붙이면 검증기는 어느 회차 숫자든 통과시킨다. 구분은 제목이 한다."""
    text = recap.combine_blocks([("S&P 500 3주 하락", "블록A"), ("VIX 30", "블록B")])
    assert "=== 1번 조건: S&P 500 3주 하락 ===" in text
    assert "=== 2번 조건: VIX 30 ===" in text
    assert text.index("블록A") < text.index("블록B")


# --- 모을 것이 모자랄 때 ----------------------------------------------

def test_one_episode_is_not_a_recap(tmp_path):
    """한 편짜리 '몰아보기'는 원 회차의 재탕이다."""
    now = datetime(2026, 9, 18, 3, tzinfo=timezone.utc)
    path = _log(tmp_path, [("2026-09-15T00:05:00+00:00", "gspc-down3", "run")])
    block, labels = run_recap.gather(
        recap.WEEK, tmp_path, path, 2, log=lambda *_: None, now=now
    )
    assert block is None and labels == []


def test_a_failed_condition_does_not_sink_the_whole_recap(tmp_path, monkeypatch):
    """야후가 하루 안 되는 것 때문에 주간 편이 사라지면 목적 자체가 없어진다."""
    now = datetime(2026, 9, 18, 3, tzinfo=timezone.utc)
    path = _log(tmp_path, [
        ("2026-09-15T00:05:00+00:00", "gspc-down3", "run"),
        ("2026-09-16T00:05:00+00:00", "gspc-drawdown20", "run"),
        ("2026-09-17T00:05:00+00:00", "vix-threshold30", "run"),
    ])

    calls = []

    def fake_block(topic, outdir, log=print):
        calls.append(topic.key)
        return None if topic.key == "gspc-drawdown20" else f"{topic.key} 블록"

    monkeypatch.setattr(run_recap, "_block_for", fake_block)
    block, labels = run_recap.gather(
        recap.WEEK, tmp_path, path, 2, log=lambda *_: None, now=now
    )

    assert len(calls) == 3           # 실패한 뒤에도 나머지를 계속 뽑는다
    assert len(labels) == 2
    assert "gspc-drawdown20" not in block


def test_a_window_already_recapped_is_not_built_twice(tmp_path, capsys):
    """같은 주를 두 번 내면 그게 바로 소재 반복이다."""
    key = recap.window_key(recap.WEEK)
    path = _log(tmp_path, [
        (datetime.now(timezone.utc).isoformat(timespec="seconds"), key, recap.RECAP_TOOL),
    ])
    code = run_recap.main([
        "--window", "week", "--outdir", str(tmp_path), "--log-path", str(path),
    ])
    assert code == 0
    assert "이미 묶었다" in capsys.readouterr().out


def test_recap_keys_never_collide_with_the_rotation_pool():
    """몰아보기 기록이 순환 풀의 소진 판정을 건드리면 안 된다."""
    pool_keys = {topic.key for topic in topics.TOPIC_POOL}
    for kind in recap.WINDOWS:
        assert recap.window_key(kind) not in pool_keys


def test_recap_key_does_not_consume_a_pool_topic(tmp_path):
    """몰아보기를 낸 주에도 다음 새 소재는 그대로 남아 있어야 한다."""
    path = _log(tmp_path, [
        ("2026-09-15T00:05:00+00:00", "recap-week-2026-W38", recap.RECAP_TOOL),
    ])
    assert topics.next_topic(path).key == topics.TOPIC_POOL[0].key
