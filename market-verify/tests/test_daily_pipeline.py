from pathlib import Path

import pytest

from src import daily_pipeline, topics
from tests.fixtures import SCRIPT

FILLED = SCRIPT.replace(
    "## 6. [운영자 코멘트]\n\n",
    "## 6. [운영자 코멘트]\n저는 그때 데이터를 안 보고 움직였습니다.\n\n",
)


def _outdir_of(argv):
    return Path(argv[argv.index("--outdir") + 1])


def fake_tool_writing_a_script(argv):
    outdir = _outdir_of(argv)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "GSPC_down-weeks_20260101-000000_script.md").write_text(FILLED, encoding="utf-8")
    return 0


@pytest.fixture
def stub_run_tool(monkeypatch):
    """토픽 'gspc-down3' 이 부르는 run.main 을 가짜로 바꾼다. 네트워크·API 를 타지 않는다."""
    monkeypatch.setitem(daily_pipeline.TOOL_MAIN, "run", fake_tool_writing_a_script)


def test_parse_args_defaults_to_the_full_pipeline():
    args = daily_pipeline.parse_args([])
    assert args.block_only is False
    assert args.silent is False
    assert args.shorts_count is None
    assert args.topic_key is None


def test_it_makes_a_longform_and_shorts_then_records_the_topic(tmp_path, stub_run_tool, capsys):
    log_path = tmp_path / "used_topics.csv"
    code = daily_pipeline.main(
        ["--outdir", str(tmp_path), "--silent", "--log-path", str(log_path),
         "--topic-key", "gspc-down3"]
    )
    out = capsys.readouterr().out

    assert code == 0
    assert len(list(tmp_path.glob("*_short*.mp4"))) == 3
    assert [p for p in tmp_path.glob("*.mp4") if "_short" not in p.name], "롱폼이 없다"
    assert topics.used_keys(log_path) == {"gspc-down3"}
    assert "업로드는 하지 않았다" in out


def test_shorts_count_limits_how_many_cuts_are_built(tmp_path, stub_run_tool):
    code = daily_pipeline.main(
        ["--outdir", str(tmp_path), "--silent", "--log-path", str(tmp_path / "log.csv"),
         "--topic-key", "gspc-down3", "--shorts-count", "1"]
    )
    assert code == 0
    assert len(list(tmp_path.glob("*_short*.mp4"))) == 1


def test_it_never_uploads(tmp_path, stub_run_tool, monkeypatch):
    monkeypatch.setattr(
        daily_pipeline.produce, "upload", lambda *a, **k: pytest.fail("업로드하면 안 된다")
    )
    code = daily_pipeline.main(
        ["--outdir", str(tmp_path), "--silent", "--log-path", str(tmp_path / "log.csv"),
         "--topic-key", "gspc-down3"]
    )
    assert code == 0


def test_block_only_stops_before_video_and_does_not_record_the_topic(tmp_path, monkeypatch, capsys):
    log_path = tmp_path / "used_topics.csv"
    monkeypatch.setitem(daily_pipeline.TOOL_MAIN, "run", lambda argv: 0)
    monkeypatch.setattr(
        daily_pipeline.produce, "build", lambda *a, **k: pytest.fail("영상을 만들면 안 된다")
    )
    code = daily_pipeline.main(
        ["--outdir", str(tmp_path), "--block-only", "--log-path", str(log_path),
         "--topic-key", "gspc-down3"]
    )
    assert code == 0
    assert "--block-only" in capsys.readouterr().out
    assert topics.used_keys(log_path) == set(), "블록만 만들고 다룬 것으로 기록하면 안 된다"


def test_block_only_is_passed_through_to_the_tool(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setitem(
        daily_pipeline.TOOL_MAIN, "run", lambda argv: seen.update(argv=argv) or 0
    )
    daily_pipeline.main(
        ["--outdir", str(tmp_path), "--block-only", "--log-path", str(tmp_path / "log.csv"),
         "--topic-key", "gspc-down3"]
    )
    assert "--block-only" in seen["argv"]


def test_a_failing_tool_stops_the_pipeline_without_recording(tmp_path, monkeypatch, capsys):
    log_path = tmp_path / "used_topics.csv"
    monkeypatch.setitem(daily_pipeline.TOOL_MAIN, "run", lambda argv: 2)
    monkeypatch.setattr(
        daily_pipeline.produce, "build", lambda *a, **k: pytest.fail("멈췄어야 한다")
    )
    code = daily_pipeline.main(
        ["--outdir", str(tmp_path), "--log-path", str(log_path), "--topic-key", "gspc-down3"]
    )
    assert code == 2
    assert "종료코드 2" in capsys.readouterr().out
    assert topics.used_keys(log_path) == set()


def test_a_missing_script_file_is_reported(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(daily_pipeline.TOOL_MAIN, "run", lambda argv: 0)
    code = daily_pipeline.main(
        ["--outdir", str(tmp_path), "--log-path", str(tmp_path / "log.csv"),
         "--topic-key", "gspc-down3"]
    )
    assert code == 3
    assert "대본 파일" in capsys.readouterr().out


def test_an_unknown_topic_key_is_rejected(tmp_path):
    with pytest.raises(KeyError):
        daily_pipeline.main(["--outdir", str(tmp_path), "--topic-key", "no-such-topic"])


def test_unreadable_shorts_cuts_are_not_silent(tmp_path, monkeypatch, capsys):
    """섹션은 있는데 한 컷도 못 읽으면, 숏폼이 0개인 줄도 모르고 지나간다."""
    monkeypatch.setitem(daily_pipeline.TOOL_MAIN, "run", fake_tool_writing_a_script)
    monkeypatch.setattr(daily_pipeline.shorts, "parse_cuts", lambda text: [])
    monkeypatch.setattr(daily_pipeline.shorts, "has_section", lambda text: True)
    code = daily_pipeline.main(
        ["--outdir", str(tmp_path), "--silent", "--log-path", str(tmp_path / "log.csv"),
         "--topic-key", "gspc-down3"]
    )
    assert code == 0
    assert "표기 형식이 바뀐 것 같다" in capsys.readouterr().out


def test_a_bad_outdir_is_reported_before_any_work(tmp_path, monkeypatch, capsys):
    """드라이브가 빠진 채 스케줄러가 돌면 스택트레이스만 남는다. 먼저 본다."""
    monkeypatch.setitem(
        daily_pipeline.TOOL_MAIN, "run", lambda argv: pytest.fail("폴더도 없이 시작했다")
    )
    monkeypatch.setattr(
        daily_pipeline, "check_outdir", lambda outdir: "저장 폴더를 쓸 수 없다: Z:\\없음"
    )
    code = daily_pipeline.main(["--outdir", "Z:\\없음", "--topic-key", "gspc-down3"])
    assert code == 2
    assert "저장 폴더를 쓸 수 없다" in capsys.readouterr().out


def test_check_outdir_accepts_a_writable_folder(tmp_path):
    assert daily_pipeline.check_outdir(tmp_path / "새폴더") is None
    assert (tmp_path / "새폴더").is_dir()
    assert not (tmp_path / "새폴더" / ".write_test").exists(), "확인용 파일을 남겼다"


def test_check_outdir_reports_an_unusable_path(tmp_path):
    # 파일을 폴더로 쓰려 하면 실패한다. 드라이브 미연결과 같은 종류의 실패다.
    blocker = tmp_path / "파일"
    blocker.write_text("", encoding="utf-8")
    problem = daily_pipeline.check_outdir(blocker)
    assert problem and "저장 폴더를 쓸 수 없다" in problem


def test_repeat_makes_several_episodes_each_with_a_new_topic(tmp_path, stub_run_tool, monkeypatch):
    log_path = tmp_path / "used_topics.csv"
    # 두 편이 서로 다른 도구를 부를 수 있으므로 전부 가짜로 바꾼다.
    for tool in list(daily_pipeline.TOOL_MAIN):
        monkeypatch.setitem(daily_pipeline.TOOL_MAIN, tool, fake_tool_writing_a_script)
    code = daily_pipeline.main(
        ["--outdir", str(tmp_path), "--silent", "--log-path", str(log_path),
         "--shorts-count", "0", "--repeat", "2"]
    )
    assert code == 0
    assert topics.used_keys(log_path) == {
        topics.TOPIC_POOL[0].key, topics.TOPIC_POOL[1].key
    }, "같은 토픽을 두 번 만들었다"


def test_repeat_stops_at_the_first_failure(tmp_path, monkeypatch, capsys):
    log_path = tmp_path / "used_topics.csv"
    for tool in list(daily_pipeline.TOOL_MAIN):
        monkeypatch.setitem(daily_pipeline.TOOL_MAIN, tool, lambda argv: 2)
    code = daily_pipeline.main(
        ["--outdir", str(tmp_path), "--log-path", str(log_path), "--repeat", "3"]
    )
    assert code == 2
    assert "만든 편수: 0" in capsys.readouterr().out
    assert topics.used_keys(log_path) == set()


def test_repeat_rejects_a_pinned_topic_and_zero(tmp_path):
    with pytest.raises(SystemExit):
        daily_pipeline.parse_args(["--repeat", "2", "--topic-key", "gspc-down3"])
    with pytest.raises(SystemExit):
        daily_pipeline.parse_args(["--repeat", "0"])


def test_without_a_topic_key_it_follows_the_rotation(tmp_path, monkeypatch):
    log_path = tmp_path / "used_topics.csv"
    topics.record_topic(topics.TOPIC_POOL[0], log_path)
    expected = topics.TOPIC_POOL[1]
    # 두 번째 토픽이 어떤 도구를 부르든 그 도구를 가짜로 바꾼다.
    monkeypatch.setitem(daily_pipeline.TOOL_MAIN, expected.tool, fake_tool_writing_a_script)
    code = daily_pipeline.main(
        ["--outdir", str(tmp_path), "--silent", "--log-path", str(log_path)]
    )
    assert code == 0
    assert topics.used_keys(log_path) == {topics.TOPIC_POOL[0].key, expected.key}
