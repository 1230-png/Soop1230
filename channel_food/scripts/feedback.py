"""실적이 나쁜 주제를 가려내는 피드백 루프.

Postgres 대신 CSV를 쓴다. 하루 1편이면 1년에 365행이라 DB를 세울 이유가 없고,
CSV는 저장소에 그대로 커밋되므로 로컬과 Actions가 같은 파일을 본다.
(대규모로 갈 때를 대비한 DB 버전은 shorts_engine/ 에 그대로 남겨 두었다.)

읽는 파일 두 개:
  metrics.csv   조회수·좋아요 스냅샷. 갱신하지 않고 계속 쌓는다 (append-only).
  used_log.csv  어떤 영상이 어떤 주제였는지.

판정 규칙 세 가지, 전부 오판을 막기 위한 것이다:
  - 조회수 min_views 미만은 표본에서 뺀다. 노출이 안 된 영상의 좋아요 비율은
    주제의 문제가 아니라 그냥 데이터가 없는 것이다.
  - 주제당 min_samples편 이상 있어야 판정한다. 없으면 운 나쁜 한 편이
    주제 하나를 영구히 배제한다.
  - 평균을 본다. 최솟값을 보면 같은 이유로 무너진다.
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

# 조회수가 이만큼은 나와야 좋아요 비율에 의미가 생긴다.
MIN_VIEWS = 500
# 주제당 최소 표본 수.
MIN_SAMPLES = 3
# 이 비율 미만이면 실패로 본다 (1%).
RATIO_THRESHOLD = 0.01

METRIC_FIELDS = [
    "fetched_at",
    "youtube_video_id",
    "content_id",
    "type",
    "view_count",
    "like_count",
    "comment_count",
]


@dataclass(frozen=True)
class TypeVerdict:
    """주제 하나에 대한 판정."""

    type: str
    samples: int          # 판정에 쓰인 영상 수 (조회수 문턱을 넘은 것만)
    avg_like_ratio: float
    failing: bool

    def describe(self) -> str:
        return f"{self.type}(표본 {self.samples}편, 좋아요 {self.avg_like_ratio * 100:.2f}%)"


def _to_int(value: str) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def load_latest_metrics(metrics_path: Path) -> dict[str, dict]:
    """영상별 가장 최근 스냅샷.

    같은 영상이 여러 번 수집돼 있으면 파일에서 마지막에 나온 행을 쓴다.
    수집은 append-only라 파일 순서가 곧 시간 순서다.
    """
    if not metrics_path.exists():
        return {}

    latest: dict[str, dict] = {}
    try:
        with open(metrics_path, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                video_id = (row.get("youtube_video_id") or "").strip()
                if video_id:
                    latest[video_id] = row
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        # 지표를 못 읽는 것은 발행을 막을 이유가 못 된다. 피드백만 끄고 넘어간다.
        print(f"[경고] 지표 파일을 읽을 수 없어 피드백을 건너뜁니다: {exc}", file=sys.stderr)
        return {}
    return latest


def load_video_types(used_log_path: Path) -> dict[str, str]:
    """업로드된 영상 id → 주제. metrics.csv의 type이 비었을 때의 근거."""
    if not used_log_path.exists():
        return {}

    types: dict[str, str] = {}
    try:
        with open(used_log_path, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                video_id = (row.get("youtube_video_id") or "").strip()
                kind = (row.get("type") or "").strip()
                if video_id and kind:
                    types[video_id] = kind
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        print(f"[경고] 업로드 로그를 읽을 수 없습니다: {exc}", file=sys.stderr)
        return {}
    return types


def evaluate_types(
    metrics_path: Path,
    used_log_path: Path,
    min_views: int = MIN_VIEWS,
    min_samples: int = MIN_SAMPLES,
    ratio_threshold: float = RATIO_THRESHOLD,
) -> list[TypeVerdict]:
    """주제별 판정 전체. 표본이 모자란 주제도 failing=False로 함께 돌려준다.

    판정 결과를 그대로 보여줄 수 있어야 "왜 이 주제가 빠졌나"를 설명할 수 있다.
    """
    latest = load_latest_metrics(metrics_path)
    fallback_types = load_video_types(used_log_path)

    buckets: dict[str, list[float]] = {}
    for video_id, row in latest.items():
        kind = (row.get("type") or "").strip() or fallback_types.get(video_id, "")
        views = _to_int(row.get("view_count", ""))
        likes = _to_int(row.get("like_count", ""))
        if not kind or views is None or likes is None:
            continue
        if views < min_views:
            continue  # 노출이 부족한 영상은 주제를 평가할 근거가 못 된다
        buckets.setdefault(kind, []).append(likes / views)

    verdicts = []
    for kind, ratios in sorted(buckets.items()):
        avg = sum(ratios) / len(ratios)
        verdicts.append(
            TypeVerdict(
                type=kind,
                samples=len(ratios),
                avg_like_ratio=avg,
                failing=len(ratios) >= min_samples and avg < ratio_threshold,
            )
        )
    return verdicts


def failing_types(metrics_path: Path, used_log_path: Path, **kwargs) -> set[str]:
    """다음 생성에서 제외할 주제 집합. 데이터가 부족하면 빈 집합."""
    return {v.type for v in evaluate_types(metrics_path, used_log_path, **kwargs) if v.failing}


def append_metrics(metrics_path: Path, rows: list[dict]) -> None:
    """스냅샷을 덧붙인다. 기존 행은 절대 고치지 않는다.

    갱신하면 성장 곡선을 잃고, 수집이 한 번 실패했을 때 멀쩡한 값이 0으로 덮인다.
    """
    if not rows:
        return
    is_new = not metrics_path.exists()
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=METRIC_FIELDS)
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in METRIC_FIELDS})


def main() -> int:
    """현황 확인용. `python3 feedback.py` 로 지금 판정 상태를 본다."""
    root = Path(__file__).resolve().parent.parent
    verdicts = evaluate_types(root / "metrics.csv", root / "used_log.csv")

    if not verdicts:
        print("표본이 아직 없습니다. 조회수 "
              f"{MIN_VIEWS} 이상인 영상이 생기면 판정이 시작됩니다.")
        print("채널 초기에는 정상입니다 — 제외 목록 없이 순서대로 발행됩니다.")
        return 0

    print(f"{'주제':<14}{'표본':>5}{'좋아요비율':>12}   판정")
    print("-" * 46)
    for v in verdicts:
        mark = "제외" if v.failing else ("판정보류" if v.samples < MIN_SAMPLES else "유지")
        print(f"{v.type:<14}{v.samples:>5}{v.avg_like_ratio * 100:>11.2f}%   {mark}")
    excluded = sorted(v.type for v in verdicts if v.failing)
    print("\n다음 생성에서 제외: " + (", ".join(excluded) if excluded else "없음"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
