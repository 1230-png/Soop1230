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


# ─── 캔들차트 화면 ────────────────────────────────────────────────────

import numpy as np
import pandas as pd
from PIL import Image as PILImage


def ohlc(bars=120, seed=7):
    rng = np.random.default_rng(seed)
    close = [100.0]
    for _ in range(bars - 1):
        close.append(close[-1] * (1 + rng.normal(0.0004, 0.016)))
    close = np.array(close)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1 + abs(rng.normal(0, 0.006, bars)))
    low = np.minimum(open_, close) * (1 - abs(rng.normal(0, 0.006, bars)))
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close},
        index=pd.bdate_range("2024-01-02", periods=bars),
    )


def colors_of(path):
    with PILImage.open(path) as image:
        return {color for _, color in image.convert("RGB").getcolors(maxcolors=1 << 24)}


def test_chart_fills_the_frame(tmp_path):
    out = render.candle_chart(ohlc(), tmp_path / "c.png")
    with PILImage.open(out) as image:
        assert image.size == (render.WIDTH, render.HEIGHT)


def test_chart_draws_both_up_and_down_candles(tmp_path):
    """오르내림이 색으로 갈려야 한다. 한 색만 나오면 그리기가 깨진 것이다."""
    out = render.candle_chart(ohlc(), tmp_path / "c.png")
    colors = colors_of(out)
    assert render.UP_COLOR in colors
    assert render.DOWN_COLOR in colors


def test_chart_background_is_dark(tmp_path):
    out = render.candle_chart(ohlc(), tmp_path / "c.png")
    with PILImage.open(out) as image:
        assert image.convert("RGB").getpixel((5, 5)) == render.CHART_BG


def test_highlight_box_is_drawn_only_when_asked(tmp_path):
    """빨간 사각형이 볼 곳을 짚는다. 참고 영상이 그렇게 한다."""
    plain = render.candle_chart(ohlc(), tmp_path / "plain.png")
    marked = render.candle_chart(ohlc(), tmp_path / "marked.png", highlight=(40, 70))
    assert render.HIGHLIGHT not in colors_of(plain)
    assert render.HIGHLIGHT in colors_of(marked)


def test_empty_data_still_produces_a_frame(tmp_path):
    empty = pd.DataFrame({"Open": [], "High": [], "Low": [], "Close": []})
    out = render.candle_chart(empty, tmp_path / "c.png")
    with PILImage.open(out) as image:
        assert image.size == (render.WIDTH, render.HEIGHT)


def test_flat_prices_do_not_divide_by_zero(tmp_path):
    flat = pd.DataFrame(
        {"Open": [100.0] * 20, "High": [100.0] * 20,
         "Low": [100.0] * 20, "Close": [100.0] * 20},
        index=pd.bdate_range("2024-01-02", periods=20),
    )
    out = render.candle_chart(flat, tmp_path / "c.png")
    assert out.exists()


def test_bottom_area_is_left_clear_for_subtitles(tmp_path):
    """자막이 앉을 자리에 캔들을 그리면 글자가 묻힌다."""
    out = render.candle_chart(ohlc(), tmp_path / "c.png")
    with PILImage.open(out) as image:
        rgb = image.convert("RGB")
        row = render.HEIGHT - 60
        assert {rgb.getpixel((x, row)) for x in range(0, render.WIDTH, 40)} == {
            render.CHART_BG
        }


def test_subtitle_writes_over_the_chart(tmp_path):
    chart = render.candle_chart(ohlc(), tmp_path / "c.png")
    before = colors_of(chart)
    render.draw_subtitle(chart, "이 구간에서 조건이 성립했습니다.")
    after = colors_of(chart)
    assert render.SUBTITLE_FG in after
    assert render.SUBTITLE_FG not in before


def test_long_narration_wraps_instead_of_running_off(tmp_path):
    chart = render.candle_chart(ohlc(), tmp_path / "c.png")
    long_line = "분포부터 봅니다. " * 8
    out = render.draw_subtitle(chart, long_line, out_path=tmp_path / "sub.png")
    with PILImage.open(out) as image:
        assert image.size == (render.WIDTH, render.HEIGHT)


def test_subtitle_can_write_to_a_separate_file(tmp_path):
    chart = render.candle_chart(ohlc(), tmp_path / "c.png")
    out = render.draw_subtitle(chart, "자막", out_path=tmp_path / "sub.png")
    assert out.exists()
    assert render.SUBTITLE_FG not in colors_of(chart), "원본은 그대로여야 한다"


def test_caption_strip_labels_what_we_are_looking_at(tmp_path):
    chart = render.candle_chart(ohlc(), tmp_path / "c.png")
    before = colors_of(chart)
    render.caption_strip(chart, "S&P 500 · 주간 종가 3주 연속 하락")
    assert colors_of(chart) != before


# ─── 움직이는 화면과 외곽선 자막 ─────────────────────────────────────

def test_subtitle_uses_a_stroke_not_a_box(tmp_path):
    """박스를 깔면 차트가 가려진다. 외곽선만 두르고 배경은 비운다."""
    chart = render.candle_chart(ohlc(), tmp_path / "c.png")
    render.draw_subtitle(chart, "이 구간에서 조건이 성립했습니다.")
    with PILImage.open(chart) as image:
        rgb = image.convert("RGB")
        row = render.HEIGHT - 175
        pixels = [rgb.getpixel((x, row)) for x in range(0, render.WIDTH, 3)]
    assert render.SUBTITLE_FG in pixels, "글자가 안 그려졌다"
    assert any(p == render.CHART_BG for p in pixels), "글자 줄이 통째로 칠해졌다"


def test_overlay_is_transparent_except_the_text(tmp_path):
    out = render.subtitle_overlay("판단은 각자.", tmp_path / "o.png")
    with PILImage.open(out) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((5, 5))[3] == 0, "배경이 투명해야 차트가 비친다"
        alphas = [image.getpixel((x, render.HEIGHT - 175))[3] for x in range(0, render.WIDTH, 3)]
    assert max(alphas) == 255


def test_overlay_can_carry_the_caption_too(tmp_path):
    plain = render.subtitle_overlay("자막", tmp_path / "a.png")
    labelled = render.subtitle_overlay("자막", tmp_path / "b.png", label="S&P 500")
    with PILImage.open(plain) as p, PILImage.open(labelled) as l:
        assert p.getpixel((80, 60))[3] == 0
        assert l.getpixel((80, 60))[3] > 0


def test_pan_width_is_wider_than_the_frame():
    """훑고 지나갈 여백이 있어야 화면이 움직인다."""
    assert render.PAN_WIDTH > render.WIDTH


def test_pan_mux_produces_a_video_of_the_audio_length(tmp_path):
    wide = render.candle_chart(
        ohlc(), tmp_path / "wide.png", width=render.PAN_WIDTH
    )
    overlay = render.subtitle_overlay("이 구간을 봅니다.", tmp_path / "o.png")
    audio = _silence(tmp_path / "a.mp3", 3)
    out = render.pan_mux(wide, overlay, audio, tmp_path / "part.mp4", 3.0)
    assert out.exists()
    assert render.audio_duration(out) == pytest.approx(3.0, abs=0.6)


def test_panned_frames_actually_differ(tmp_path):
    """crop 창이 안 움직이면 정지 화면과 같다. 첫 프레임과 끝 프레임을 비교한다."""
    wide = render.candle_chart(ohlc(), tmp_path / "wide.png", width=render.PAN_WIDTH)
    overlay = render.subtitle_overlay("자막", tmp_path / "o.png")
    audio = _silence(tmp_path / "a.mp3", 4)
    video = render.pan_mux(wide, overlay, audio, tmp_path / "p.mp4", 4.0)

    frames = []
    for label, when in (("first", "0"), ("last", "3.5")):
        path = tmp_path / f"{label}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", when, "-i", str(video),
             "-frames:v", "1", str(path)],
            check=True, capture_output=True,
        )
        with PILImage.open(path) as image:
            frames.append(image.convert("RGB").tobytes())
    assert frames[0] != frames[1], "화면이 움직이지 않았다"


def test_zero_length_scene_does_not_break_the_pan(tmp_path):
    wide = render.candle_chart(ohlc(), tmp_path / "wide.png", width=render.PAN_WIDTH)
    overlay = render.subtitle_overlay("자막", tmp_path / "o.png")
    audio = _silence(tmp_path / "a.mp3", 1)
    assert render.pan_mux(wide, overlay, audio, tmp_path / "p.mp4", 0.0).exists()
