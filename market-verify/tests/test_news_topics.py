import pandas as pd
import pytest

from src import daily_pipeline, news_topics, topics


def series(values, start="2026-01-01"):
    return pd.Series(
        [float(v) for v in values], index=pd.bdate_range(start, periods=len(values))
    )


def fetch_returning(table):
    def fetch(ticker, start, end=None):
        if ticker not in table:
            raise ValueError(f"{ticker} 데이터를 받지 못했다.")
        return series(table[ticker])
    return fetch


def test_recent_moves_ranks_by_size_of_the_move():
    fetch = fetch_returning({"^GSPC": [100, 99], "BTC-USD": [100, 90], "^VIX": [20, 21]})
    moves = news_topics.recent_moves(
        (("^GSPC", "S&P 500", "1990-01-01"),
         ("BTC-USD", "비트코인", "2015-01-01"),
         ("^VIX", "VIX", "1990-01-01")),
        fetch=fetch, log=lambda *a: None,
    )
    assert [m.ticker for m in moves] == ["BTC-USD", "^VIX", "^GSPC"]
    assert moves[0].change_pct == pytest.approx(-10.0)


def test_a_ticker_that_fails_does_not_sink_the_whole_run():
    fetch = fetch_returning({"^GSPC": [100, 97]})
    moves = news_topics.recent_moves(
        (("없는티커", "없음", "1990-01-01"), ("^GSPC", "S&P 500", "1990-01-01")),
        fetch=fetch, log=lambda *a: None,
    )
    assert [m.ticker for m in moves] == ["^GSPC"]


def test_a_drop_becomes_a_drawdown_check():
    move = news_topics.Move("BTC-USD", "비트코인", "2015-01-01", -7.2, 60000.0, "2026-09-14")
    topic = news_topics.topic_for(move)
    assert topic.tool == "run"
    assert "--condition" in topic.argv and "drawdown" in topic.argv
    assert "비트코인" in topic.label


def test_a_rise_becomes_a_down_weeks_check():
    move = news_topics.Move("^GSPC", "S&P 500", "1990-01-01", 2.4, 5000.0, "2026-09-14")
    topic = news_topics.topic_for(move)
    assert "down-weeks" in topic.argv


def test_vix_uses_the_threshold_below_its_current_level():
    move = news_topics.Move("^VIX", "VIX", "1990-01-01", 18.0, 33.0, "2026-09-14")
    topic = news_topics.topic_for(move)
    assert "threshold" in topic.argv
    assert topic.argv[topic.argv.index("--level") + 1] == "30"


def test_a_quiet_day_falls_back_to_the_pool():
    """어제 별일 없었는데 억지로 화제를 만들지 않는다."""
    fetch = fetch_returning({"^GSPC": [100, 100.2]})
    found = news_topics.topic_from_yesterday(
        (("^GSPC", "S&P 500", "1990-01-01"),), fetch=fetch, log=lambda *a: None
    )
    assert found is None


def test_an_already_covered_topic_is_skipped():
    fetch = fetch_returning({"^GSPC": [100, 90], "BTC-USD": [100, 95]})
    watchlist = (("^GSPC", "S&P 500", "1990-01-01"), ("BTC-USD", "비트코인", "2015-01-01"))
    first = news_topics.topic_from_yesterday(watchlist, fetch=fetch, log=lambda *a: None)
    second = news_topics.topic_from_yesterday(
        watchlist, fetch=fetch, used={first.key}, log=lambda *a: None
    )
    assert second is not None and second.key != first.key


def test_pipeline_defaults_to_news_and_falls_back_to_the_pool(tmp_path, monkeypatch):
    args = daily_pipeline.parse_args(["--log-path", str(tmp_path / "log.csv")])
    assert args.source == "news"
    monkeypatch.setattr(news_topics, "topic_from_yesterday", lambda **k: None)
    assert daily_pipeline.pick_topic(args) == topics.TOPIC_POOL[0]


def test_pipeline_uses_the_news_topic_when_there_is_one(tmp_path, monkeypatch):
    args = daily_pipeline.parse_args(["--log-path", str(tmp_path / "log.csv")])
    picked = topics.Topic("news-x", "run", ("--ticker", "X"), "어제 크게 움직인 X")
    monkeypatch.setattr(news_topics, "topic_from_yesterday", lambda **k: picked)
    assert daily_pipeline.pick_topic(args) == picked


def test_source_pool_never_looks_at_the_news(tmp_path, monkeypatch):
    args = daily_pipeline.parse_args(
        ["--source", "pool", "--log-path", str(tmp_path / "log.csv")]
    )
    monkeypatch.setattr(
        news_topics, "topic_from_yesterday",
        lambda **k: pytest.fail("pool 인데 뉴스를 봤다"),
    )
    assert daily_pipeline.pick_topic(args) == topics.TOPIC_POOL[0]
