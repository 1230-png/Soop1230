"""build_timeline 단위 테스트.

ffmpeg 없이 도는 순수 함수라, 렌더링 로직 중 유일하게 완전히 고정할 수 있는 부분이다.
경계 조건을 여기서 잡지 못하면 실제 영상에서 화면이 스쳐 지나가거나
자막과 음성이 어긋난 채로 업로드된다.
"""

import pytest

from render.timeline import Cut, build_timeline, total_duration, variant_count

HOOK_SEC = 3.0
HOOK_CUT = 0.5


def hook_cuts(cuts, hook_sec=HOOK_SEC):
    """훅 구간(0~hook_sec)에 걸린 컷들."""
    out, t = [], 0.0
    for c in cuts:
        if t >= hook_sec - 1e-9:
            break
        out.append(c)
        t += c.duration
    return out


class TestHookWindow:
    def test_첫_3초는_0_5초씩_여섯_컷(self):
        cuts = build_timeline([5.0, 4.0, 4.0])
        first = hook_cuts(cuts)
        assert len(first) == 6
        assert all(c.duration == pytest.approx(0.5) for c in first)
        assert total_duration(first) == pytest.approx(3.0)

    def test_훅_구간_배경은_매_컷_바뀐다(self):
        cuts = build_timeline([5.0, 4.0])
        variants = [c.variant for c in hook_cuts(cuts)]
        assert len(set(variants)) == len(variants), "훅 구간 배경이 반복되면 빠른 컷 효과가 없다"

    def test_훅_구간_자막은_실제_음성을_따른다(self):
        # 0.8초짜리 문장 뒤에 긴 문장. 훅 구간이 두 문장에 걸친다.
        cuts = build_timeline([0.8, 6.0])
        first = hook_cuts(cuts)
        # 0.0~0.5는 0번, 0.5~0.8도 0번, 그 뒤로는 1번이어야 한다
        assert first[0].segment_index == 0
        assert first[1].segment_index == 0
        assert first[2].segment_index == 1, "0.8초 이후에는 두 번째 문장이 읽히고 있다"

    def test_컷_간격은_바꿀_수_있다(self):
        cuts = build_timeline([10.0], hook_sec=2.0, hook_cut=0.25)
        first = hook_cuts(cuts, hook_sec=2.0)
        assert len(first) == 8
        assert all(c.duration == pytest.approx(0.25) for c in first)


class TestDynamicLength:
    @pytest.mark.parametrize(
        "durations",
        [[5.0, 4.0, 4.0], [2.0, 2.0], [40.0], [1.0] * 20, [3.7, 8.2, 5.5, 9.1]],
    )
    def test_총합이_나레이션_길이와_일치(self, durations):
        cuts = build_timeline(durations)
        assert total_duration(cuts) == pytest.approx(sum(durations), abs=1e-6)

    def test_30초_고정이_아니다(self):
        short = build_timeline([2.0, 2.0])
        long = build_timeline([20.0, 20.0])
        assert total_duration(short) == pytest.approx(4.0)
        assert total_duration(long) == pytest.approx(40.0)


class TestSegmentAlignment:
    def test_훅_이후는_문장_경계를_지킨다(self):
        cuts = build_timeline([5.0, 4.0, 6.0])
        after = cuts[6:]  # 훅 6컷 이후
        assert [c.segment_index for c in after] == [0, 1, 2]
        # 0번 문장은 5초 중 3초를 훅에서 썼으므로 2초가 남는다
        assert after[0].duration == pytest.approx(2.0)
        assert after[1].duration == pytest.approx(4.0)
        assert after[2].duration == pytest.approx(6.0)

    def test_훅에_완전히_먹힌_문장은_다시_안_나온다(self):
        # 앞 두 문장 합이 2.0초라 3초 훅 안에 모두 소비된다
        cuts = build_timeline([1.0, 1.0, 10.0])
        after = cuts[6:]
        assert [c.segment_index for c in after] == [2], "이미 지나간 문장을 다시 띄우면 안 된다"

    def test_모든_문장이_한_번은_등장한다(self):
        durations = [4.0, 3.0, 5.0, 2.0]
        cuts = build_timeline(durations)
        shown = {c.segment_index for c in cuts}
        assert shown == set(range(len(durations)))


class TestEdgeCases:
    def test_전체가_훅보다_짧으면_훅을_줄인다(self):
        cuts = build_timeline([1.2])
        assert total_duration(cuts) == pytest.approx(1.2)
        # 0.5 + 0.5 + 0.2
        assert [round(c.duration, 2) for c in cuts] == [0.5, 0.5, 0.2]

    def test_문장이_하나뿐이어도_동작한다(self):
        cuts = build_timeline([10.0])
        assert total_duration(cuts) == pytest.approx(10.0)
        assert all(c.segment_index == 0 for c in cuts)

    def test_ffprobe가_0을_돌려줘도_화면이_스쳐가지_않는다(self):
        # probe_duration은 실패 시 0.0을 돌려준다. 그대로 쓰면 0초짜리 컷이 생긴다.
        cuts = build_timeline([0.0, 0.0, 5.0], min_segment_sec=0.35)
        assert all(c.duration > 0 for c in cuts)
        assert total_duration(cuts) == pytest.approx(0.35 + 0.35 + 5.0)

    def test_훅이_0이면_전부_문장_경계를_따른다(self):
        cuts = build_timeline([2.0, 3.0], hook_sec=0.0)
        assert [(c.segment_index, c.duration) for c in cuts] == [(0, 2.0), (1, 3.0)]

    def test_빈_입력은_거부한다(self):
        with pytest.raises(ValueError, match="비어"):
            build_timeline([])

    @pytest.mark.parametrize("bad", [0, -0.5])
    def test_컷_간격이_0_이하면_거부한다(self, bad):
        # 막지 않으면 while 루프가 무한히 돈다
        with pytest.raises(ValueError, match="양수"):
            build_timeline([5.0], hook_cut=bad)

    def test_음수_훅은_거부한다(self):
        with pytest.raises(ValueError, match="음수"):
            build_timeline([5.0], hook_sec=-1.0)


class TestRendererContract:
    def test_variant는_0부터_빈틈없이_증가한다(self):
        cuts = build_timeline([5.0, 4.0, 3.0])
        variants = [c.variant for c in cuts]
        assert variants == list(range(len(cuts))), "렌더러가 모듈로로 대응시키므로 연속이어야 한다"
        assert variant_count(cuts) == len(cuts)

    def test_모든_컷의_길이는_양수(self):
        for durations in ([0.0], [0.5, 0.5], [3.0], [2.999], [100.0]):
            cuts = build_timeline(durations)
            assert all(c.duration > 0 for c in cuts), f"{durations}에서 0초 컷 발생"

    def test_Cut은_불변이다(self):
        cut = Cut(0, 0, 1.0)
        with pytest.raises(Exception):
            cut.duration = 2.0  # type: ignore[misc]
