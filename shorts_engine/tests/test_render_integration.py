"""렌더러 통합 테스트.

edge-tts와 Pexels는 네트워크가 필요해 여기서는 스텁으로 대체한다.
검증 대상은 그 바깥 전부다 — 타임라인이 실제 파일로 옮겨지는지,
영상 길이가 나레이션을 따라가는지, 첫 3초에 컷이 실제로 6개 들어가는지.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from render import media, renderer
from render.renderer import RenderRequest

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe 필요",
)


def _tone(path: Path, seconds: float) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"sine=f=330:d={seconds:.2f}",
         "-q:a", "5", "-acodec", "libmp3lame", str(path)],
        check=True, capture_output=True,
    )


@pytest.fixture
def stub_media(monkeypatch):
    """TTS와 배경 사진만 대체한다. ffmpeg 경로는 진짜로 돈다."""

    def fake_tts(lang, text, out_path, use_elevenlabs_for_en=True):
        # 한국어 낭독 속도를 대략 초당 6음절로 흉내낸다.
        _tone(Path(out_path), max(1.0, len(text) / 6.0))

    monkeypatch.setattr(media, "tts_save_segment", fake_tts)
    monkeypatch.setattr(renderer.media, "tts_save_segment", fake_tts)
    # 네트워크를 타지 않게 한다 → 그라데이션 배경으로 되돌아간다
    monkeypatch.setattr(renderer.media, "fetch_background_photo", lambda q, p: None)


@pytest.fixture
def request_obj():
    return RenderRequest(
        script_id=1,
        title="시계 초침이 멈춰 보이는 이유",
        hook="시계를 봤는데 초침이 멈춰 있었던 적 있나요?",
        body=[
            "고개를 돌려 시계를 본 순간, 초침이 유난히 오래 멈춰 있는 것처럼 느껴집니다.",
            "크로노스타시스라는 이름이 붙은 실제 현상입니다.",
            "눈이 빠르게 움직이는 동안의 빈 시간을 뇌가 메웁니다.",
        ],
        cta_question="여러분도 이런 순간을 겪어본 적 있나요?",
        image_query="clock face macro dark",
    )


def probe(path: Path, stream: str = "format=duration") -> str:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", stream,
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip().splitlines()[0]


class TestRender:
    def test_영상이_실제로_만들어진다(self, tmp_path, stub_media, request_obj):
        out = tmp_path / "out.mp4"
        result = renderer.render(request_obj, out, tmp_path / "work")

        assert out.exists() and out.stat().st_size > 0
        assert result.cut_count > 6

    def test_길이가_나레이션을_따른다(self, tmp_path, stub_media, request_obj):
        out = tmp_path / "out.mp4"
        result = renderer.render(request_obj, out, tmp_path / "work")

        actual = float(probe(out))
        # 30초 고정이 아니라 계산된 길이와 맞아야 한다
        assert actual == pytest.approx(result.duration_sec, abs=0.5)
        assert abs(actual - 30.0) > 1.0, "30초 고정이면 동적 계산이 안 된 것"

    def test_첫_3초에_컷이_여섯_번_들어간다(self, tmp_path, stub_media, request_obj):
        out = tmp_path / "out.mp4"
        result = renderer.render(request_obj, out, tmp_path / "work")
        assert result.hook_cut_count == 6

    def test_세로_해상도와_오디오_스트림(self, tmp_path, stub_media, request_obj):
        out = tmp_path / "out.mp4"
        renderer.render(request_obj, out, tmp_path / "work")

        assert probe(out, "stream=width") == "1080"
        codecs = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
             "-of", "csv=p=0", str(out)],
            check=True, capture_output=True, text=True,
        ).stdout
        assert "video" in codecs and "audio" in codecs

    def test_디코딩_오류가_없다(self, tmp_path, stub_media, request_obj):
        out = tmp_path / "out.mp4"
        renderer.render(request_obj, out, tmp_path / "work")
        err = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(out), "-f", "null", "-"],
            capture_output=True, text=True,
        ).stderr.strip()
        assert err == "", f"디코딩 오류: {err}"

    def test_배경_사진이_없어도_렌더링된다(self, tmp_path, stub_media, request_obj):
        # PEXELS_API_KEY가 없는 환경에서도 파이프라인이 멈추면 안 된다
        result = renderer.render(request_obj, tmp_path / "out.mp4", tmp_path / "work")
        assert result.used_photo is False
        assert (tmp_path / "out.mp4").exists()

    def test_짧은_대본도_처리한다(self, tmp_path, stub_media):
        req = RenderRequest(
            script_id=2, title="짧은 것", hook="짧은 훅",
            body=["한 문장.", "두 문장."], cta_question="어떠세요?",
            image_query="dark abstract",
        )
        result = renderer.render(req, tmp_path / "s.mp4", tmp_path / "w")
        assert (tmp_path / "s.mp4").exists()
        assert result.duration_sec > 0

    def test_마지막_컷이_잘리지_않는다(self, tmp_path, stub_media, request_obj):
        # concat demuxer는 마지막 duration을 무시한다. 마지막 장을 한 번 더
        # 적지 않으면 영상이 계산값보다 짧게 끝난다.
        out = tmp_path / "out.mp4"
        result = renderer.render(request_obj, out, tmp_path / "work")
        assert float(probe(out)) >= result.duration_sec - 0.5
