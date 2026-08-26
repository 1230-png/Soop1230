"""피드백 판정 테스트.

여기서 막고 싶은 사고는 하나다: 표본이 부족한데 주제를 배제해 버리는 것.
한 번 배제된 주제는 발행이 멈추므로 스스로 회복할 기회도 사라진다.
"""

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import cta  # noqa: E402
import feedback  # noqa: E402


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def metric(video_id, kind, views, likes, fetched_at="2026-08-26T00:00:00+00:00"):
    return {
        "fetched_at": fetched_at,
        "youtube_video_id": video_id,
        "content_id": video_id.lstrip("v"),
        "type": kind,
        "view_count": views,
        "like_count": likes,
        "comment_count": 0,
    }


@pytest.fixture
def paths(tmp_path):
    return tmp_path / "metrics.csv", tmp_path / "used_log.csv"


def test_no_files_means_no_exclusions(paths):
    """지표가 없으면 아무것도 배제하지 않는다. 채널 초기의 정상 상태."""
    assert feedback.failing_types(*paths) == set()


def test_two_samples_is_not_enough(paths):
    """표본 2편으로는 판정하지 않는다. 운 나쁜 한두 편이 주제를 죽이면 안 된다."""
    metrics, used = paths
    write_csv(metrics, feedback.METRIC_FIELDS, [
        metric("v1", "mandela", 5000, 5),   # 0.1%
        metric("v2", "mandela", 6000, 3),   # 0.05%
    ])
    used.write_text("date,content_id,type,youtube_video_id,status\n", encoding="utf-8")
    assert feedback.failing_types(metrics, used) == set()


def test_three_bad_samples_excludes_the_type(paths):
    metrics, used = paths
    write_csv(metrics, feedback.METRIC_FIELDS, [
        metric("v1", "mandela", 5000, 5),
        metric("v2", "mandela", 6000, 3),
        metric("v3", "mandela", 4000, 4),
    ])
    used.write_text("date,content_id,type,youtube_video_id,status\n", encoding="utf-8")
    assert feedback.failing_types(metrics, used) == {"mandela"}


def test_good_ratio_survives(paths):
    """좋아요 비율이 문턱을 넘으면 표본이 많아도 배제되지 않는다."""
    metrics, used = paths
    write_csv(metrics, feedback.METRIC_FIELDS, [
        metric(f"v{i}", "perception", 5000, 150) for i in range(5)  # 3%
    ])
    used.write_text("date,content_id,type,youtube_video_id,status\n", encoding="utf-8")
    assert feedback.failing_types(metrics, used) == set()


def test_low_view_videos_are_not_counted(paths):
    """조회수가 낮은 영상은 표본에서 뺀다.

    노출이 안 된 영상의 좋아요 0은 주제의 문제가 아니라 데이터가 없는 것이다.
    이걸 세면 신규 채널의 모든 주제가 즉시 배제된다.
    """
    metrics, used = paths
    write_csv(metrics, feedback.METRIC_FIELDS, [
        metric("v1", "mandela", 10, 0),
        metric("v2", "mandela", 20, 0),
        metric("v3", "mandela", 30, 0),
    ])
    used.write_text("date,content_id,type,youtube_video_id,status\n", encoding="utf-8")
    assert feedback.failing_types(metrics, used) == set()
    assert feedback.evaluate_types(metrics, used) == []


def test_average_not_minimum(paths):
    """한 편이 0이어도 평균이 문턱을 넘으면 유지한다."""
    metrics, used = paths
    write_csv(metrics, feedback.METRIC_FIELDS, [
        metric("v1", "unexplained", 5000, 0),     # 0%
        metric("v2", "unexplained", 5000, 300),   # 6%
        metric("v3", "unexplained", 5000, 300),   # 6%
    ])
    used.write_text("date,content_id,type,youtube_video_id,status\n", encoding="utf-8")
    assert feedback.failing_types(metrics, used) == set()


def test_latest_snapshot_wins(paths):
    """같은 영상이 여러 번 수집돼 있으면 마지막 행을 쓴다.

    지표는 append-only라 초기 스냅샷은 대부분 조회수가 낮다.
    옛 행을 쓰면 성장한 영상이 계속 실패로 남는다.
    """
    metrics, used = paths
    write_csv(metrics, feedback.METRIC_FIELDS, [
        metric("v1", "perception", 100, 0, "2026-08-01T00:00:00+00:00"),
        metric("v1", "perception", 9000, 450, "2026-08-26T00:00:00+00:00"),  # 5%
    ])
    used.write_text("date,content_id,type,youtube_video_id,status\n", encoding="utf-8")
    latest = feedback.load_latest_metrics(metrics)
    assert latest["v1"]["view_count"] == "9000"


def test_type_falls_back_to_used_log(paths):
    """metrics.csv의 type이 비어 있으면 used_log.csv에서 찾는다."""
    metrics, used = paths
    rows = [metric(f"v{i}", "", 5000, 5) for i in range(3)]
    write_csv(metrics, feedback.METRIC_FIELDS, rows)
    write_csv(used, ["date", "content_id", "type", "youtube_video_id", "status"], [
        {"date": "", "content_id": str(i), "type": "mandela",
         "youtube_video_id": f"v{i}", "status": "uploaded"}
        for i in range(3)
    ])
    assert feedback.failing_types(metrics, used) == {"mandela"}


def test_corrupt_metrics_does_not_raise(paths):
    """지표 파일이 깨져도 발행은 계속돼야 한다. 피드백만 꺼진다."""
    metrics, used = paths
    metrics.write_bytes(b"\xff\xfe\x00\x00 broken")
    assert feedback.failing_types(metrics, used) == set()


def test_non_numeric_rows_are_skipped(paths):
    metrics, used = paths
    write_csv(metrics, feedback.METRIC_FIELDS, [
        {**metric("v1", "mandela", 5000, 5), "view_count": "없음"},
        metric("v2", "mandela", 5000, 5),
    ])
    used.write_text("date,content_id,type,youtube_video_id,status\n", encoding="utf-8")
    verdicts = feedback.evaluate_types(metrics, used)
    assert [v.samples for v in verdicts] == [1]


def test_append_never_rewrites(paths):
    """append_metrics는 기존 행을 건드리지 않는다."""
    metrics, _used = paths
    feedback.append_metrics(metrics, [metric("v1", "perception", 100, 1)])
    feedback.append_metrics(metrics, [metric("v1", "perception", 900, 40)])
    text = metrics.read_text(encoding="utf-8")
    assert text.count("v1") == 2
    assert text.count("fetched_at") == 1  # 헤더는 한 번만


def test_append_empty_is_noop(paths):
    metrics, _used = paths
    feedback.append_metrics(metrics, [])
    assert not metrics.exists()


def test_verdicts_explain_themselves(paths):
    metrics, used = paths
    write_csv(metrics, feedback.METRIC_FIELDS, [
        metric(f"v{i}", "mandela", 5000, 5) for i in range(3)
    ])
    used.write_text("date,content_id,type,youtube_video_id,status\n", encoding="utf-8")
    (verdict,) = feedback.evaluate_types(metrics, used)
    assert verdict.failing is True
    assert "mandela" in verdict.describe()
    assert "0.10%" in verdict.describe()


# ---------------------------------------------------------------- CTA


def test_cta_is_stable_across_runs():
    """같은 항목은 항상 같은 질문. hash()를 쓰면 실행마다 바뀐다."""
    item = {"id": 7, "type": "perception"}
    assert cta.pick(item) == cta.pick(item)


def test_cta_matches_the_type():
    assert cta.pick({"id": 1, "type": "mandela"}) in cta.QUESTIONS["mandela"]
    assert cta.pick({"id": 1, "type": "perception"}) in cta.QUESTIONS["perception"]


def test_cta_unknown_type_falls_back():
    assert cta.pick({"id": 1, "type": "무슨주제"}) in cta.FALLBACK


def test_cta_override_wins():
    item = {"id": 1, "type": "mandela", "cta": "직접 쓴 질문인가요?"}
    assert cta.pick(item) == "직접 쓴 질문인가요?"


def test_every_bank_item_gets_a_question():
    import json
    bank = Path(__file__).resolve().parent.parent / "scripts" / "weird_content.json"
    items = json.loads(bank.read_text(encoding="utf-8"))
    for item in items:
        question = cta.pick(item)
        assert question.endswith(("?", ".", "요.")), item["id"]
        assert len(question) <= 40, item["id"]
