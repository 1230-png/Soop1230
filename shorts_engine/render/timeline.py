"""컷 타임라인 계산.

렌더링에서 가장 실수하기 쉬운 부분이라 ffmpeg 의존성 없는 순수 함수로 분리했다.
여기만 단위 테스트로 고정해 두면 렌더러는 이 결과를 파일로 옮기기만 하면 된다.

두 가지 요구를 동시에 만족해야 한다:
1. 영상 길이는 30초 고정이 아니라 나레이션 길이를 따른다.
2. 첫 3초는 시청자 이탈을 막기 위해 0.5초 간격으로 화면이 바뀐다.

2번 때문에 화면 전환과 문장 경계가 어긋난다. 그래서 컷마다
"어느 문장을 띄울지"(segment_index)와 "어느 배경을 쓸지"(variant)를 따로 들고 간다.
훅 구간에서는 같은 문장이 배경만 바뀌며 여러 컷에 걸쳐 유지된다.
"""

from __future__ import annotations

from dataclasses import dataclass

# 부동소수 누적 오차 때문에 경계 비교가 흔들리는 것을 막는다.
_EPS = 1e-9


@dataclass(frozen=True)
class Cut:
    """화면에 한 장이 떠 있는 구간."""

    segment_index: int  # 이 컷 동안 읽히는 나레이션 문장 번호 (자막용)
    variant: int        # 배경 변형 번호. 렌더러가 준비한 풀에 모듈로로 대응시킨다
    duration: float     # 표시 시간(초)


def build_timeline(
    segment_durations: list[float],
    hook_sec: float = 3.0,
    hook_cut: float = 0.5,
    min_segment_sec: float = 0.35,
) -> list[Cut]:
    """나레이션 구간 길이 목록에서 컷 목록을 만든다.

    Args:
        segment_durations: 문장별 나레이션 길이(초). ffprobe 측정값.
        hook_sec: 빠른 컷을 적용할 앞부분 길이.
        hook_cut: 훅 구간에서의 컷 간격.
        min_segment_sec: 구간 길이의 하한. ffprobe가 실패해 0.0을 돌려줘도
            화면이 스쳐 지나가지 않도록 보장한다.

    Returns:
        Cut 목록. 전체 합은 보정된 나레이션 총 길이와 같다.

    Raises:
        ValueError: 구간이 비었거나 파라미터가 0 이하일 때.
    """
    if not segment_durations:
        raise ValueError("segment_durations가 비어 있습니다")
    if hook_cut <= 0:
        raise ValueError(f"hook_cut은 양수여야 합니다: {hook_cut}")
    if hook_sec < 0:
        raise ValueError(f"hook_sec은 음수일 수 없습니다: {hook_sec}")

    # ffprobe 실패(0.0)나 비정상 값을 여기서 한 번에 걷어낸다.
    durations = [max(float(d), min_segment_sec) for d in segment_durations]
    total = sum(durations)

    # 나레이션이 훅 구간보다 짧으면 훅을 전체 길이로 줄인다.
    hook_end = min(hook_sec, total)

    starts: list[float] = []
    acc = 0.0
    for d in durations:
        starts.append(acc)
        acc += d

    def segment_at(time: float) -> int:
        """time 시점에 읽히고 있는 문장 번호."""
        idx = 0
        for i, start in enumerate(starts):
            if start <= time + _EPS:
                idx = i
            else:
                break
        return idx

    cuts: list[Cut] = []
    variant = 0

    # 훅 구간: 문장 경계를 무시하고 일정 간격으로 자른다.
    t = 0.0
    while t < hook_end - _EPS:
        piece = min(hook_cut, hook_end - t)
        cuts.append(Cut(segment_at(t), variant, piece))
        variant += 1
        t += piece

    # 훅 이후: 문장 경계에 맞춘다. 화면 문장과 들리는 문장이 어긋나면 안 된다.
    for i, d in enumerate(durations):
        seg_start = starts[i]
        seg_end = seg_start + d
        if seg_end <= hook_end + _EPS:
            continue  # 훅 구간에서 이미 소비된 문장
        piece_start = max(seg_start, hook_end)
        cuts.append(Cut(i, variant, seg_end - piece_start))
        variant += 1

    return cuts


def total_duration(cuts: list[Cut]) -> float:
    return sum(c.duration for c in cuts)


def variant_count(cuts: list[Cut]) -> int:
    """렌더러가 준비해야 할 배경 변형의 최대 개수."""
    return len({c.variant for c in cuts})
