import pytest

from src import topics


def test_pool_has_unique_keys():
    keys = [topic.key for topic in topics.TOPIC_POOL]
    assert len(keys) == len(set(keys))


def test_used_keys_is_empty_when_log_is_missing(tmp_path):
    assert topics.used_keys(tmp_path / "no_such_log.csv") == set()


def test_next_topic_starts_at_the_first_pool_entry(tmp_path):
    log_path = tmp_path / "used_topics.csv"
    assert topics.next_topic(log_path) == topics.TOPIC_POOL[0]


def test_next_topic_skips_already_used_keys(tmp_path):
    log_path = tmp_path / "used_topics.csv"
    topics.record_topic(topics.TOPIC_POOL[0], log_path)
    assert topics.next_topic(log_path) == topics.TOPIC_POOL[1]


def test_next_topic_cycles_back_once_the_pool_is_exhausted(tmp_path):
    log_path = tmp_path / "used_topics.csv"
    for topic in topics.TOPIC_POOL:
        topics.record_topic(topic, log_path)
    assert topics.next_topic(log_path) == topics.TOPIC_POOL[0]


def test_record_topic_is_append_only_with_a_single_header(tmp_path):
    log_path = tmp_path / "used_topics.csv"
    topics.record_topic(topics.TOPIC_POOL[0], log_path)
    topics.record_topic(topics.TOPIC_POOL[1], log_path)
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "date,key,tool,label"
    assert len(lines) == 3
    assert topics.used_keys(log_path) == {topics.TOPIC_POOL[0].key, topics.TOPIC_POOL[1].key}


def test_topic_by_key_finds_the_matching_topic():
    found = topics.topic_by_key("btc-dilution")
    assert found.tool == "run_tokenomics"


def test_topic_by_key_rejects_an_unknown_key():
    with pytest.raises(KeyError):
        topics.topic_by_key("no-such-topic")
