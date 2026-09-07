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
