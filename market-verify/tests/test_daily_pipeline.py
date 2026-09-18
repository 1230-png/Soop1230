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
    assert "업로드하지 않았다" in out, "--upload 없이 올라갔다"


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
    # --source pool 을 준다. 기본값 news 는 news_topics 가 야후로 나가는 경로라
    # 테스트가 네트워크를 타고, 어제 움직임이 크면 순환 풀 대신 뉴스 토픽을 골라
    # 아래 단언이 깨진다. 이 테스트가 보는 것은 풀 순환이지 소재 출처가 아니다.
    code = daily_pipeline.main(
        ["--outdir", str(tmp_path), "--silent", "--log-path", str(log_path),
         "--shorts-count", "0", "--repeat", "2", "--source", "pool"]
    )
    assert code == 0
    assert topics.used_keys(log_path) == {
        topics.TOPIC_POOL[0].key, topics.TOPIC_POOL[1].key
    }, "같은 토픽을 두 번 만들었다"


def test_repeat_stops_at_the_first_failure(tmp_path, monkeypatch, capsys):
    log_path = tmp_path / "used_topics.csv"
    for tool in list(daily_pipeline.TOOL_MAIN):
        monkeypatch.setitem(daily_pipeline.TOOL_MAIN, tool, lambda argv: 2)
    # --source pool 을 준다. 기본값 news 는 news_topics 가 야후로 나가는 경로라
    # 테스트가 네트워크를 타고, 어제 움직임이 크면 순환 풀 대신 뉴스 토픽을 골라
    # 아래 단언이 깨진다. 이 테스트가 보는 것은 풀 순환이지 소재 출처가 아니다.
    code = daily_pipeline.main(
        ["--outdir", str(tmp_path), "--log-path", str(log_path), "--repeat", "3",
         "--source", "pool"]
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
    # --source pool 을 준다. 기본값 news 는 news_topics 가 야후로 나가는 경로라
    # 테스트가 네트워크를 타고, 어제 움직임이 크면 순환 풀 대신 뉴스 토픽을 골라
    # 아래 단언이 깨진다. 이 테스트가 보는 것은 풀 순환이지 소재 출처가 아니다.
    code = daily_pipeline.main(
        ["--outdir", str(tmp_path), "--silent", "--log-path", str(log_path),
         "--source", "pool"]
    )
    assert code == 0
    assert topics.used_keys(log_path) == {topics.TOPIC_POOL[0].key, expected.key}


# --- 업로드 ---------------------------------------------------------------
# 형제 채널(run_shorts.yml)은 이미 무인 발행한다. market-verify 만 사람 손을 탔다.


class FakeUpload:
    """올린 것을 기록만 한다. 네트워크를 타지 않는다."""

    def __init__(self, fail_on=()):
        self.fail_on = tuple(fail_on)
        self.calls = []

    def __call__(self, video_path, title, description, tags=(), privacy="private",
                 thumbnail_path=None, **_):
        if Path(video_path).name in self.fail_on:
            raise RuntimeError("업로드 중 끊겼다")
        self.calls.append({"path": Path(video_path).name, "title": title,
                           "privacy": privacy, "thumb": thumbnail_path})
        return f"id-{len(self.calls)}"


def upload_args(**over):
    args = daily_pipeline.parse_args([])
    for key, value in over.items():
        setattr(args, key, value)
    return args


def test_parse_args_does_not_upload_unless_asked():
    args = daily_pipeline.parse_args([])
    assert args.upload is False
    assert args.privacy == "private", "기본값이 공개면 실수로 발행된다"


def test_short_title_keeps_the_shorts_tag_when_the_title_is_long():
    """제목은 100자까지다. 뒤에서 잘리면 #Shorts 가 날아가고 일반 영상으로 올라간다."""
    title = daily_pipeline.short_title("가" * 120, 2)
    assert len(title) <= 100
    assert title.endswith("#Shorts")


def test_upload_all_sends_the_longform_and_every_short(monkeypatch, tmp_path):
    sender = FakeUpload()
    monkeypatch.setattr(daily_pipeline.upload, "upload", sender)
    long_path = tmp_path / "v.mp4"
    shorts_paths = [tmp_path / "v_short1.mp4", tmp_path / "v_short2.mp4"]

    code = daily_pipeline.upload_all(
        FILLED, long_path, tmp_path / "v.jpg", shorts_paths,
        upload_args(upload=True, privacy="public"),
    )

    assert code == 0
    assert [call["path"] for call in sender.calls] == [
        "v.mp4", "v_short1.mp4", "v_short2.mp4"
    ]
    assert all(call["privacy"] == "public" for call in sender.calls)
    # 썸네일은 롱폼에만 붙는다. 숏폼은 세로라 가로 썸네일이 맞지 않는다.
    assert sender.calls[0]["thumb"] is not None
    assert sender.calls[1]["thumb"] is None
    assert sender.calls[1]["title"].endswith("#Shorts")


def test_upload_all_keeps_going_when_one_video_fails(monkeypatch, tmp_path, capsys):
    """한 편이 막혔다고 그날 발행이 통째로 없어지는 것이 더 나쁘다."""
    sender = FakeUpload(fail_on=("v_short1.mp4",))
    monkeypatch.setattr(daily_pipeline.upload, "upload", sender)

    code = daily_pipeline.upload_all(
        FILLED, tmp_path / "v.mp4", None,
        [tmp_path / "v_short1.mp4", tmp_path / "v_short2.mp4"],
        upload_args(upload=True, privacy="public"),
    )

    assert code == 0, "나머지가 올라갔으면 실패가 아니다"
    assert [call["path"] for call in sender.calls] == ["v.mp4", "v_short2.mp4"]
    assert "성공 2개, 실패 1개" in capsys.readouterr().out


def test_upload_all_reports_failure_when_nothing_went_up(monkeypatch, tmp_path):
    """하나도 못 올렸는데 종료코드 0 이면 로그만 보고 올라간 줄 안다."""
    sender = FakeUpload(fail_on=("v.mp4",))
    monkeypatch.setattr(daily_pipeline.upload, "upload", sender)
    code = daily_pipeline.upload_all(
        FILLED, tmp_path / "v.mp4", None, [], upload_args(upload=True)
    )
    assert code != 0


def test_it_checks_credentials_before_spending_five_minutes(monkeypatch, capsys):
    """다 만들고 나서 자격 증명이 없다고 하면 그 시간이 버려진다."""
    monkeypatch.setattr(daily_pipeline.upload, "check_credentials", lambda: "자격 증명이 없다")
    called = []
    monkeypatch.setattr(daily_pipeline, "pick_topic", lambda a: called.append(1))

    assert daily_pipeline.run_once(upload_args(upload=True)) == 2
    assert called == [], "자격 증명이 없는데 토픽부터 골랐다"
    assert "자격 증명이 없다" in capsys.readouterr().out


# --- 할당량 -----------------------------------------------------------------
# 유튜브 일일 할당량은 구글 클라우드 프로젝트 단위다. 이 저장소는 채널을 여럿
# 굴리므로 한 프로젝트를 같이 쓰면 서로의 몫을 깎는다.


class QuotaError(Exception):
    """googleapiclient 가 돌려주는 모양을 흉내낸다. 타입이 아니라 문구로 구분된다."""

    def __init__(self):
        super().__init__(
            '<HttpError 403 "The request cannot be completed because you have '
            'exceeded your <a href="/youtube/v3/getting-started#quota">quota</a>.">'
            " Reason: quotaExceeded"
        )


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Reason: quotaExceeded", True),
        ("dailyLimitExceeded", True),
        ("Quota exceeded for quota metric", True),
        ("HttpError 403 ... Reason: forbidden", False),
        ("연결이 끊겼다", False),
    ],
)
def test_is_quota_error_reads_the_message_not_the_type(message, expected):
    assert daily_pipeline.is_quota_error(Exception(message)) is expected


def test_upload_all_stops_the_moment_the_quota_runs_out(monkeypatch, tmp_path, capsys):
    """남은 것도 전부 떨어진다. 계속 두드려봐야 같은 에러만 쌓인다."""
    attempted = []

    def sender(video_path, **_):
        attempted.append(Path(video_path).name)
        if len(attempted) == 2:
            raise QuotaError()
        return "id"

    monkeypatch.setattr(daily_pipeline.upload, "upload", sender)
    code = daily_pipeline.upload_all(
        FILLED, tmp_path / "v.mp4", None,
        [tmp_path / f"v_short{n}.mp4" for n in (1, 2, 3)],
        upload_args(upload=True, privacy="public"),
    )

    assert attempted == ["v.mp4", "v_short1.mp4"], "할당량이 떨어졌는데 계속 올렸다"
    out = capsys.readouterr().out
    assert "남은 2편은 시도하지 않는다" in out
    assert "프로젝트 단위" in out, "왜 떨어졌는지 짚어주지 않으면 원인을 못 찾는다"
    assert "성공 1개, 실패 3개" in out, "시도하지 않은 것도 실패로 세야 한다"
    assert code == 0, "한 편이라도 올라갔으면 실패가 아니다"


def test_upload_all_does_not_stop_on_an_ordinary_failure(monkeypatch, tmp_path):
    """할당량이 아닌 실패는 그 한 편만 건너뛴다."""
    sender = FakeUpload(fail_on=("v_short1.mp4",))
    monkeypatch.setattr(daily_pipeline.upload, "upload", sender)
    daily_pipeline.upload_all(
        FILLED, tmp_path / "v.mp4", None,
        [tmp_path / "v_short1.mp4", tmp_path / "v_short2.mp4"],
        upload_args(upload=True),
    )
    assert [call["path"] for call in sender.calls] == ["v.mp4", "v_short2.mp4"]
