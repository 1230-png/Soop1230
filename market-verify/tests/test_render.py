import subprocess

import pytest
from PIL import Image

from src import render


def test_finds_a_korean_font():
    assert render.find_korean_font()


def test_slide_has_full_hd_size(tmp_path):
    out = render.slide("주간 종가 3주 연속 하락", "1. 오프닝", tmp_path / "s.png")
    with Image.open(out) as image:
        assert image.size == (render.WIDTH, render.HEIGHT)


def test_slide_actually_draws_something(tmp_path):
    """글자가 안 그려지면 배경색 한 가지만 남는다."""
    out = render.slide("사례 59건", "3. 과거 사례", tmp_path / "s.png")
    with Image.open(out) as image:
        colors = image.convert("RGB").getcolors(maxcolors=1 << 24)
    assert len(colors) > 50, "그라데이션과 글자가 보이지 않는다"


def test_long_screen_text_is_wrapped_not_clipped(tmp_path):
    long_text = "주간 종가가 세 번 연속으로 내려간 시점을 모두 모아 이후 흐름을 확인한다"
    out = render.slide(long_text, "2. 조건 설정", tmp_path / "s.png")
    with Image.open(out) as image:
        assert image.size == (render.WIDTH, render.HEIGHT)


def test_thumbnail_is_youtube_sized(tmp_path):
    out = render.thumbnail("3주 연속 하락 이후 12개월", tmp_path / "t.jpg", subtitle="과거 사례 검증")
    with Image.open(out) as image:
        assert image.size == (render.THUMB_WIDTH, render.THUMB_HEIGHT)


# --- 썸네일 분포 조각 --------------------------------------------------------
#
# 글자만 있는 썸네일은 추천 목록에서 옆 영상과 구분되지 않는다. 아래쪽에 분포를
# 한 줄로 얹는다. 조각이 실제로 그려졌는지는 그 자리의 짙은 점을 세어 본다 —
# 좌표를 하나하나 확인하면 판을 조금만 바꿔도 시험이 깨진다.

THUMB_SERIES = [
    ("21거래일(1개월)", [-5.2, 2.3, -1.4, 3.8, 0.5, -2.2, 6.1, -0.3]),
    ("252거래일(12개월)", [12.1, 25.4, -8.9, 18.3, 6.7, -14.2, 21.0, 3.3]),
]
# 제목이 길면 글자가 조각 자리까지 내려온다. 그때는 조각을 포기한다.
LONG_TITLE = "S&P 500 주간 종가가 3주 연속 하락한 시점 이후 12개월 지표 변화를 전부 확인한다"


def _ink_below_the_fold(path):
    """조각 자리(아래쪽)의 짙은 픽셀 수. 미색 종이만 있으면 0 에 가깝다.

    종이 결은 매번 새로 뿌려지므로 두 장을 바이트로 비교할 수 없다. 세어서 본다.
    """
    with Image.open(path) as image:
        band = image.convert("L").crop(
            (0, int(render.THUMB_HEIGHT * render.THUMB_STRIP_TOP),
             render.THUMB_WIDTH, render.THUMB_HEIGHT)
        )
    return sum(band.histogram()[:140])


def test_thumbnail_with_a_chart_is_still_youtube_sized(tmp_path):
    out = render.thumbnail("3주 연속 하락 이후 12개월은?", tmp_path / "t.jpg",
                           subtitle="머니로직", series=THUMB_SERIES)
    with Image.open(out) as image:
        assert image.size == (render.THUMB_WIDTH, render.THUMB_HEIGHT)


def test_the_chart_fragment_actually_gets_drawn(tmp_path):
    plain = render.thumbnail("3주 연속 하락 이후 12개월은?", tmp_path / "plain.jpg",
                             subtitle="머니로직")
    charted = render.thumbnail("3주 연속 하락 이후 12개월은?", tmp_path / "chart.jpg",
                               subtitle="머니로직", series=THUMB_SERIES)
    assert _ink_below_the_fold(charted) > _ink_below_the_fold(plain) + 500


def _strip_spy(monkeypatch):
    """조각을 그렸는지, 그렸다면 어느 구간으로 그렸는지만 본다."""
    seen = []
    monkeypatch.setattr(
        render, "_thumbnail_strip",
        lambda draw, name, values, *args: seen.append(name),
    )
    return seen


def test_a_long_title_drops_the_fragment_instead_of_overlapping(monkeypatch, tmp_path):
    """겹쳐 찍힌 썸네일이 조각 없는 썸네일보다 나쁘다."""
    seen = _strip_spy(monkeypatch)
    render.thumbnail(LONG_TITLE, tmp_path / "l.jpg", subtitle="머니로직", series=THUMB_SERIES)
    assert seen == []

    render.thumbnail("3주 연속 하락 이후 12개월은?", tmp_path / "s.jpg",
                     subtitle="머니로직", series=THUMB_SERIES)
    assert len(seen) == 1, "짧은 제목에는 조각이 들어가야 한다"


def test_the_fragment_uses_the_longest_horizon(monkeypatch, tmp_path):
    """블록의 마지막 구간이 가장 긴 기간이다. 짧은 구간은 점이 0 에 뭉친다."""
    seen = _strip_spy(monkeypatch)
    render.thumbnail("무엇이 있었나?", tmp_path / "t.jpg", series=THUMB_SERIES)
    assert seen == ["252거래일(12개월)"]


def _silence(path, seconds):
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", str(seconds), "-q:a", "9", str(path)],
        check=True, capture_output=True,
    )
    return path


def test_audio_duration_reads_the_real_length(tmp_path):
    path = _silence(tmp_path / "a.mp3", 3)
    assert render.audio_duration(path) == pytest.approx(3.0, abs=0.3)


def test_mux_produces_a_playable_video(tmp_path):
    image = render.slide("사례 59건", "3. 과거 사례", tmp_path / "s.png")
    audio = _silence(tmp_path / "a.mp3", 2)
    out = render.mux(image, audio, tmp_path / "part.mp4")
    assert out.exists() and out.stat().st_size > 0
    assert render.audio_duration(out) == pytest.approx(2.0, abs=0.5)


def test_concat_adds_the_parts_up(tmp_path):
    parts = []
    for index, seconds in enumerate([2, 3], start=1):
        image = render.slide(f"장면 {index}", "테스트", tmp_path / f"s{index}.png")
        audio = _silence(tmp_path / f"a{index}.mp3", seconds)
        parts.append(render.mux(image, audio, tmp_path / f"p{index}.mp4"))
    out = render.concat(parts, tmp_path / "all.mp4", tmp_path)
    assert render.audio_duration(out) == pytest.approx(5.0, abs=0.8)


def test_concat_cleans_up_its_list_file(tmp_path):
    image = render.slide("장면", "테스트", tmp_path / "s.png")
    audio = _silence(tmp_path / "a.mp3", 1)
    part = render.mux(image, audio, tmp_path / "p.mp4")
    render.concat([part], tmp_path / "all.mp4", tmp_path)
    assert not (tmp_path / "parts.txt").exists()


# --- 느린 확대 ----------------------------------------------------------
#
# 필터 문자열만 검사한다. ffmpeg 를 돌리지 않으므로 어디서나 돈다.


def _frames(filter_text):
    return int(filter_text.split(":d=")[1].split(":")[0])


def _step(filter_text):
    return float(filter_text.split("min(1+")[1].split("*on")[0])


def test_zoom_pulls_toward_the_centre():
    """zoompan 기본값은 왼쪽 위로 당긴다. 글자가 한쪽으로 쏠려 보인다."""
    text = render.zoom_filter(1920, 1080, 10)
    assert "x='iw/2-(iw/zoom/2)'" in text
    assert "y='ih/2-(ih/zoom/2)'" in text


def test_zoom_keeps_the_original_output_size():
    """미리 키운 크기가 결과로 새어 나가면 concat 이 토막을 못 잇는다."""
    assert ":s=1920x1080:" in render.zoom_filter(1920, 1080, 10)
    assert ":s=1080x1920:" in render.zoom_filter(1080, 1920, 10)


def test_prescale_is_even_on_both_sides():
    """yuv420p 는 홀수 크기를 거부한다."""
    scale = render.zoom_filter(1081, 1921, 10).split(",")[0]
    width, height = scale.removeprefix("scale=").split(":")[:2]
    assert int(width) % 2 == 0
    assert int(height) % 2 == 0


def test_prescale_is_larger_than_the_zoom_ever_needs():
    """상한보다 작게 키우면 끝에서 화면이 뭉개진다."""
    scale = render.zoom_filter(1920, 1080, 10).split(",")[0]
    width = int(scale.removeprefix("scale=").split(":")[0])
    assert width >= 1920 * render.ZOOM_MAX


def test_longer_audio_gets_more_frames():
    """프레임을 모자라게 잡으면 zoompan 이 확대를 처음부터 다시 시작해 화면이 튄다."""
    assert _frames(render.zoom_filter(1920, 1080, 60)) > _frames(
        render.zoom_filter(1920, 1080, 5)
    )


def test_frames_cover_the_whole_clip_with_room_to_spare():
    seconds = 42
    text = render.zoom_filter(1920, 1080, seconds)
    assert _frames(text) > seconds * render.FPS


def test_zoom_reaches_the_cap_exactly_and_no_further():
    """상한 계산이 틀리면 끝에서 글자가 흐려지거나, 아예 안 움직인다."""
    text = render.zoom_filter(1920, 1080, 30)
    assert 1 + _step(text) * _frames(text) == pytest.approx(render.ZOOM_MAX, rel=1e-6)


def test_zoom_is_gentle_enough_to_go_unnoticed():
    """눈에 띄면 그것대로 산만하다. 정지 화면 느낌만 없애는 정도다."""
    assert 1.0 < render.ZOOM_MAX <= 1.15
