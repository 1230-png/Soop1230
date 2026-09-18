"""생성기가 피드백 판정과 타임라인을 실제로 반영하는지 본다.

여기 있는 테스트는 ffmpeg도 edge-tts도 부르지 않는다. 순수 선택 로직과
컷 계산만 확인한다 — 렌더링은 test_render.py 쪽이다.
"""

import csv
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import feedback  # noqa: E402
from timeline import build_timeline  # noqa: E402

# 생성기 본체는 아직 저장소에 없고 로컬에만 있다. 모듈 수준에서 그냥 import 하면
# 수집 단계에서 이 파일이 터지고, pytest 는 거기서 전체 실행을 멈춘다 — 그래서
# tests/ 의 다른 파일까지 한 개도 돌지 않았다. 없을 때는 이 파일의 해당
# 테스트만 건너뛰고 나머지는 계속 돌게 한다.
#
# 모듈 자체가 없을 때만 봐준다. 파일은 있는데 그 안의 import 가 깨진 경우는
# 그대로 터뜨린다 — 생성기를 들고 있는 로컬에서 진짜 고장을 "건너뜀"으로
# 덮어버리면 이 장치가 오히려 해가 된다.
try:
    import generate_weird_video as gen  # noqa: E402
except ModuleNotFoundError as exc:
    if exc.name != "generate_weird_video":
        raise
    gen = None

needs_generator = pytest.mark.skipif(
    gen is None,
    reason="scripts/generate_weird_video.py 가 저장소에 없다 (로컬 전용)",
)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """콘텐츠 뱅크·로그를 임시 파일로 갈아끼운다."""
    bank = tmp_path / "content.json"
    used = tmp_path / "used_log.csv"
    metrics = tmp_path / "metrics.csv"
    monkeypatch.setattr(gen, "CONTENT_BANK", bank)
    monkeypatch.setattr(gen, "USED_LOG", used)
    monkeypatch.setattr(gen, "METRICS_LOG", metrics)
    return bank, used, metrics


def put_bank(path, items):
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")


def put_used(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=gen.LOG_FIELDS)
        w.writeheader()
        w.writerows(rows)


def put_metrics(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=feedback.METRIC_FIELDS)
        w.writeheader()
        w.writerows(rows)


def bad_metric(video_id, kind):
    return {
        "fetched_at": "2026-08-26T00:00:00+00:00", "youtube_video_id": video_id,
        "content_id": "", "type": kind, "view_count": 5000,
        "like_count": 5, "comment_count": 0,
    }


@needs_generator
def test_picks_lowest_unused_id(sandbox):
    bank, used, _m = sandbox
    put_bank(bank, [{"id": 3, "type": "a"}, {"id": 1, "type": "a"}, {"id": 2, "type": "a"}])
    put_used(used, [])
    assert gen.pick_unused_content()["id"] == 1


@needs_generator
def test_only_uploaded_rows_retire_content(sandbox):
    """업로드가 막힌 편은 다시 시도해야 한다.

    status=generated인 행까지 소진 처리하면 업로드가 한 번 실패한 콘텐츠가
    영영 방송되지 않는다.
    """
    bank, used, _m = sandbox
    put_bank(bank, [{"id": 1, "type": "a"}, {"id": 2, "type": "a"}])
    put_used(used, [
        {"date": "", "content_id": "1", "type": "a", "title": "", "video_path": "",
         "youtube_video_id": "", "status": "generated"},
    ])
    assert gen.pick_unused_content()["id"] == 1


@needs_generator
def test_exhausted_bank_returns_none(sandbox):
    """소진되면 처음으로 돌아가지 않는다. 같은 영상을 두 번 올리지 않기 위해서다."""
    bank, used, _m = sandbox
    put_bank(bank, [{"id": 1, "type": "a"}])
    put_used(used, [
        {"date": "", "content_id": "1", "type": "a", "title": "", "video_path": "",
         "youtube_video_id": "x", "status": "uploaded"},
    ])
    assert gen.pick_unused_content() is None


@needs_generator
def test_failing_type_is_skipped(sandbox):
    """실적이 나쁜 주제는 id가 더 작아도 건너뛴다."""
    bank, used, metrics = sandbox
    put_bank(bank, [{"id": 1, "type": "mandela"}, {"id": 2, "type": "perception"}])
    put_used(used, [])
    put_metrics(metrics, [bad_metric(f"v{i}", "mandela") for i in range(3)])
    assert gen.pick_unused_content()["id"] == 2


@needs_generator
def test_all_types_failing_still_publishes(sandbox):
    """제외하고 나면 아무것도 안 남는 경우, 발행을 멈추지 않는다.

    피드백은 순서를 바꾸는 장치이지 발행을 세우는 장치가 아니다.
    """
    bank, used, metrics = sandbox
    put_bank(bank, [{"id": 1, "type": "mandela"}, {"id": 2, "type": "mandela"}])
    put_used(used, [])
    put_metrics(metrics, [bad_metric(f"v{i}", "mandela") for i in range(3)])
    assert gen.pick_unused_content()["id"] == 1


@needs_generator
def test_segments_end_with_a_question(sandbox):
    item = {"id": 1, "type": "perception", "hook": "훅", "body": ["본문1", "본문2"],
            "twist": "반전"}
    segments = gen.narration_segments(item)
    roles = [r for r, _t in segments]
    assert roles == ["hook", "body", "body", "twist", "cta"]
    assert segments[-1][1].endswith(("?", "."))


def test_hook_window_has_six_half_second_cuts():
    """앞 3초가 0.5초씩 여섯 컷. 이탈 방어의 핵심이라 여기서 고정한다."""
    cuts = build_timeline([4.0, 3.0, 3.0], hook_sec=3.0, hook_cut=0.5)
    hook = [c for c in cuts if c.duration <= 0.5 + 1e-9]
    assert len(hook) == 6
    assert sum(c.duration for c in hook) == pytest.approx(3.0)


def test_hook_cuts_show_the_first_sentence():
    """빠른 컷 구간에도 자막은 그때 들리는 문장이어야 한다."""
    cuts = build_timeline([4.0, 3.0], hook_sec=3.0, hook_cut=0.5)
    assert all(c.segment_index == 0 for c in cuts[:6])


def test_hook_cuts_use_different_backgrounds():
    """같은 배경이 반복되면 컷이 바뀐 것으로 보이지 않는다."""
    cuts = build_timeline([4.0, 3.0], hook_sec=3.0, hook_cut=0.5)
    assert len({c.variant for c in cuts[:6]}) == 6


def test_total_duration_follows_narration():
    """30초 고정이 아니다. 총 길이는 나레이션 합과 같아야 한다."""
    durations = [4.2, 3.1, 2.8, 5.0]
    cuts = build_timeline(durations, hook_sec=3.0, hook_cut=0.5)
    assert sum(c.duration for c in cuts) == pytest.approx(sum(durations))


def test_short_narration_clamps_the_hook():
    """전체가 3초보다 짧으면 훅 구간을 전체 길이로 줄인다."""
    cuts = build_timeline([1.2], hook_sec=3.0, hook_cut=0.5)
    assert sum(c.duration for c in cuts) == pytest.approx(1.2)
    assert [c.duration for c in cuts] == pytest.approx([0.5, 0.5, 0.2])


@needs_generator
def test_unmeasurable_segment_gets_a_floor():
    """ffprobe가 0.0을 돌려줘도 슬라이드가 스쳐 지나가면 안 된다."""
    cuts = build_timeline([0.0, 4.0], hook_sec=3.0, hook_cut=0.5,
                          min_segment_sec=gen.MIN_SEGMENT_SEC)
    assert sum(c.duration for c in cuts) == pytest.approx(gen.MIN_SEGMENT_SEC + 4.0)


@needs_generator
def test_adjacent_backgrounds_always_differ():
    """이웃한 두 컷의 배경이 같으면 컷이 바뀐 것으로 보이지 않는다.

    팔레트를 crc32로 매번 뽑던 때는 실제로 같은 색이 연달아 나왔다.
    사진이 없어 그라데이션으로 되돌아간 경우가 특히 위험하다.
    """
    from PIL import ImageChops, ImageStat

    for content_id in range(1, 12):
        backgrounds = gen.build_backgrounds({"id": content_id}, 8, None)
        for i in range(1, len(backgrounds)):
            diff = ImageStat.Stat(
                ImageChops.difference(backgrounds[i], backgrounds[i - 1])
            ).mean
            assert sum(diff) / 3 > 1.0, f"#{content_id} 변형 {i - 1}과 {i}가 사실상 같다"


@needs_generator
def test_background_count_is_capped():
    """컷이 아무리 많아도 배경 변형은 상한을 넘지 않는다.

    확대로 만들기 때문에 무한정 늘리면 뒤쪽 변형의 화질이 무너진다.
    """
    assert len(gen.build_backgrounds({"id": 1}, 999, None)) == gen.MAX_VARIANTS
