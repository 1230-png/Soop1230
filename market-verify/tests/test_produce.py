from pathlib import Path

import pytest

from src import brand, produce, render, voice
from tests.fixtures import SCRIPT

FILLED = SCRIPT.replace(
    "## 6. [운영자 코멘트]\n\n",
    "## 6. [운영자 코멘트]\n저는 그때 데이터를 안 보고 움직였습니다.\n\n",
)


def test_parse_args_defaults_to_private_and_no_upload():
    args = produce.parse_args(["--script", "a.md"])
    assert args.privacy == "private"
    assert args.upload is False


def test_public_must_be_asked_for_explicitly():
    assert produce.parse_args(["--script", "a.md", "--privacy", "public"]).privacy == "public"
    with pytest.raises(SystemExit):
        produce.parse_args(["--script", "a.md", "--privacy", "everyone"])


def test_build_produces_a_video_and_thumbnail(tmp_path):
    video, thumb = produce.build(
        FILLED, tmp_path, "demo", voice.silent_speak, voice.DEFAULT_VOICE, log=lambda *a: None
    )
    assert video.exists() and thumb.exists()
    assert video.suffix == ".mp4" and thumb.suffix == ".jpg"
    assert render.audio_duration(video) > 30, "장면이 통째로 빠졌다"


def test_build_warns_when_the_operator_note_is_empty(tmp_path):
    lines = []
    produce.build(SCRIPT, tmp_path, "demo", voice.silent_speak, voice.DEFAULT_VOICE, log=lines.append)
    assert any("비어 있다" in line for line in lines)


def test_build_stays_quiet_when_the_note_is_filled(tmp_path):
    lines = []
    produce.build(FILLED, tmp_path, "demo", voice.silent_speak, voice.DEFAULT_VOICE, log=lines.append)
    # 장면 진행 로그에도 섹션 이름이 나오므로 경고 문구로 판별한다.
    assert not any("비어 있다" in line for line in lines)


def test_build_rejects_a_script_with_no_narration(tmp_path):
    with pytest.raises(ValueError):
        produce.build("헤더가 없는 글", tmp_path, "demo", voice.silent_speak,
                      voice.DEFAULT_VOICE, log=lambda *a: None)


def test_missing_script_file_stops_before_any_work(tmp_path, capsys):
    code = produce.main(["--script", str(tmp_path / "없다.md"), "--outdir", str(tmp_path)])
    assert code == 2
    assert "대본을 찾지 못했다" in capsys.readouterr().out


def test_upload_credentials_are_checked_before_rendering(tmp_path, monkeypatch, capsys):
    """다 만들고 나서 자격 증명이 없다고 하면 시간만 버린다."""
    script = tmp_path / "s_script.md"
    script.write_text(FILLED, encoding="utf-8")
    monkeypatch.setattr(produce, "check_credentials", lambda: "자격 증명이 없다")
    monkeypatch.setattr(
        produce, "build", lambda *a, **k: pytest.fail("자격 증명 없이 렌더링을 시작했다")
    )
    code = produce.main(["--script", str(script), "--outdir", str(tmp_path), "--upload"])
    assert code == 2
    assert "자격 증명이 없다" in capsys.readouterr().out


def test_no_upload_flag_means_no_upload(tmp_path, monkeypatch, capsys):
    script = tmp_path / "s_script.md"
    script.write_text(FILLED, encoding="utf-8")
    monkeypatch.setattr(produce, "upload", lambda *a, **k: pytest.fail("올리면 안 된다"))
    code = produce.main(["--script", str(script), "--outdir", str(tmp_path), "--silent"])
    assert code == 0
    assert "업로드하지 않았다" in capsys.readouterr().out


def test_upload_reports_the_link_and_the_private_reminder(tmp_path, monkeypatch, capsys):
    script = tmp_path / "s_script.md"
    script.write_text(FILLED, encoding="utf-8")
    monkeypatch.setattr(produce, "check_credentials", lambda: None)
    monkeypatch.setattr(produce, "upload", lambda *a, **k: "VID123")
    code = produce.main(
        ["--script", str(script), "--outdir", str(tmp_path), "--silent", "--upload"]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "youtu.be/VID123" in out
    assert "비공개 상태다" in out


def test_upload_passes_private_by_default(tmp_path, monkeypatch):
    script = tmp_path / "s_script.md"
    script.write_text(FILLED, encoding="utf-8")
    seen = {}
    monkeypatch.setattr(produce, "check_credentials", lambda: None)

    def fake_upload(video_path, **kwargs):
        seen.update(kwargs)
        return "VID"

    monkeypatch.setattr(produce, "upload", fake_upload)
    produce.main(["--script", str(script), "--outdir", str(tmp_path), "--silent", "--upload"])
    assert seen["privacy"] == "private"
    assert seen["title"].startswith("S&P 500")
    assert "투자 권유나 조언이 아닙니다" in seen["description"]
    # 채널 표준 면책 문구가 영상마다 함께 나가야 한다.
    assert seen["description"].endswith(brand.DISCLAIMER)
    assert brand.NAME in seen["tags"]


# --- 결과 구간의 분포 그림 ----------------------------------------------
#
# 그리기는 갈아끼운다. 여기서 보는 것은 "어느 화면을 골랐나"이지 그림 자체가 아니다.
# 덕분에 한글 폰트 없이도 돈다.

from src.script_parse import Scene  # noqa: E402

SERIES = [("21거래일(1개월)", [-12.3, 4.1, -1.0, 7.7])]


def _spy(monkeypatch):
    picked = []
    monkeypatch.setattr(
        produce.render, "distribution_slide",
        lambda series, caption, section, path: picked.append(("그림", section)) or path,
    )
    monkeypatch.setattr(
        produce.render, "slide",
        lambda text, section, path: picked.append(("글자", section)) or path,
    )
    return picked


def test_the_result_section_gets_the_chart_and_others_stay_text(monkeypatch, tmp_path):
    picked = _spy(monkeypatch)

    produce._scene_image(Scene("4. 결과", "화면", "가"), SERIES, tmp_path / "a.png", print)
    produce._scene_image(Scene("2. 조건 설정", "화면", "가"), SERIES, tmp_path / "b.png", print)
    produce._scene_image(Scene("1. 오프닝", "화면", "가"), SERIES, tmp_path / "c.png", print)

    assert picked == [("그림", "4. 결과"), ("글자", "2. 조건 설정"), ("글자", "1. 오프닝")]


def test_without_case_data_every_scene_stays_text(monkeypatch, tmp_path):
    """전략·토크노믹스 블록에는 사례 표가 없다. 그때도 영상은 나와야 한다."""
    picked = _spy(monkeypatch)

    produce._scene_image(Scene("4. 결과", "화면", "가"), [], tmp_path / "a.png", print)

    assert picked == [("글자", "4. 결과")]


def test_a_failed_chart_falls_back_to_text_and_says_why(monkeypatch, tmp_path):
    """그림 하나 때문에 그날 영상이 통째로 안 나오면 안 된다. 다만 조용히 넘어가지도 않는다."""
    lines = []

    def boom(*args, **kwargs):
        raise RuntimeError("폰트를 찾지 못했다")

    monkeypatch.setattr(produce.render, "distribution_slide", boom)
    monkeypatch.setattr(produce.render, "slide", lambda text, section, path: path)

    result = produce._scene_image(
        Scene("4. 결과", "화면", "가"), SERIES, tmp_path / "a.png", lines.append
    )

    assert result == tmp_path / "a.png"
    assert any("분포 그림 실패" in line for line in lines)


def test_block_is_found_beside_the_script(tmp_path):
    """run.py 가 대본과 같은 stem 으로 써 둔다."""
    script = tmp_path / "IXIC_down-weeks_20260918-2359_script.md"
    script.write_text("대본", encoding="utf-8")
    (tmp_path / "IXIC_down-weeks_20260918-2359_block.txt").write_text(
        "블록", encoding="utf-8"
    )

    assert produce.block_beside(script) == "블록"


def test_a_missing_block_is_not_an_error(tmp_path):
    script = tmp_path / "x_script.md"
    script.write_text("대본", encoding="utf-8")

    assert produce.block_beside(script) is None


# --- 썸네일 ------------------------------------------------------------
#
# 썸네일도 같은 사례 표에서 그린다. 여기서 다시 계산하면 목록에서 본 그림과
# 눌러서 본 그림이 갈라진다.

def _block_with_cases():
    """사례 표가 들어 있는 진짜 블록. 형식이 바뀌면 여기서 깨져야 한다."""
    import pandas as pd

    from src import market_events

    rows = [
        {
            "date": pd.Timestamp(date),
            "returns": dict(zip([h for h, _ in market_events.HORIZONS], values)),
        }
        for date, *values in [
            ("2008-09-12", -12.34, -5.67, 3.21),
            ("2011-08-05", 4.12, 8.90, 15.00),
            ("2018-10-26", -1.00, 2.50, 7.75),
            ("2020-03-06", -9.99, 22.10, 40.20),
        ]
    ]
    return market_events.to_block(
        ticker="^IXIC", condition="주간 종가 3주 연속 하락", rows=rows,
        summary=market_events.summarize(rows),
        data_start="1990-01-02", data_end="2026-09-04", asof="2026-09-05",
    )


def _thumbnail_spy(monkeypatch):
    seen = {}

    def fake(title, path, subtitle=None, series=None):
        seen["series"] = series
        Path(path).write_bytes(b"")
        return Path(path)

    monkeypatch.setattr(produce.render, "thumbnail", fake)
    return seen


def test_the_thumbnail_gets_the_same_case_data_as_the_video(monkeypatch, tmp_path):
    seen = _thumbnail_spy(monkeypatch)

    produce.build(FILLED, tmp_path, "demo", voice.silent_speak, voice.DEFAULT_VOICE,
                  log=lambda *a: None, block_text=_block_with_cases())

    assert [name for name, _ in seen["series"]], "썸네일에 사례 표가 넘어가지 않았다"
    assert all(len(values) == 4 for _, values in seen["series"])


def test_a_block_without_cases_leaves_the_thumbnail_plain(monkeypatch, tmp_path):
    """전략·토크노믹스 블록에는 사례 표가 없다. 그때도 썸네일은 나와야 한다."""
    seen = _thumbnail_spy(monkeypatch)

    produce.build(FILLED, tmp_path, "demo", voice.silent_speak, voice.DEFAULT_VOICE,
                  log=lambda *a: None)

    assert seen["series"] == []
