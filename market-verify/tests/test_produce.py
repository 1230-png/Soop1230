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
