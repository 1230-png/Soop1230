"""moviepy를 이용한 영상 렌더링 및 합성.

FastAPI BackgroundTasks로 실행되므로 CPU 블로킹을 피할 수 없다.
따라서 moviepy 호출을 별도 프로세스로 실행하거나 비동기 처리한다.
"""

import asyncio
import math
from pathlib import Path

import numpy as np
from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoClip,
)
from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings


WIDTH, HEIGHT = 1920, 1080
INTRO_SEC = 2.0
OUTRO_SEC = 2.0
CHANNEL_NAME = "머니로직"


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """한글 폰트를 로드한다."""
    candidates = [
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "C:\\Windows\\Fonts\\malgun.ttf",  # Windows
    ]

    for path_str in candidates:
        try:
            return ImageFont.truetype(path_str, size=size)
        except:
            continue

    return ImageFont.load_default()


def make_background() -> Image.Image:
    """단색 다크 배경 생성."""
    return Image.new("RGB", (WIDTH, HEIGHT), (15, 23, 42))


def make_title_card(ticker: str, topic: str, date_str: str) -> Image.Image:
    """타이틀 카드 생성."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 반투명 배경
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=(15, 23, 42, 200))

    # 텍스트 렌더링
    ticker_font = load_font(120, bold=True)
    topic_font = load_font(48)
    date_font = load_font(32)

    # 종목 코드
    draw.text((100, 300), ticker, fill=(56, 189, 248), font=ticker_font)

    # 주제
    draw.text((100, 500), topic[:50], fill=(255, 255, 255), font=topic_font)

    # 날짜
    draw.text((100, 650), date_str, fill=(150, 150, 150), font=date_font)

    return img


def make_subtitle(text: str) -> Image.Image:
    """자막 생성."""
    img = Image.new("RGBA", (WIDTH, 150), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 반투명 배경
    draw.rectangle([(0, 0), (WIDTH, 150)], fill=(15, 23, 42, 220))

    # 자막 텍스트
    font = load_font(36)
    draw.text((60, 30), text[:100], fill=(255, 255, 255), font=font)

    return img


def make_keyword_label(keyword: str) -> Image.Image:
    """키워드 라벨 생성."""
    img = Image.new("RGBA", (400, 60), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 노란 배경
    draw.rectangle([(0, 0), (400, 60)], fill=(234, 179, 8))

    # 텍스트
    font = load_font(28, bold=True)
    draw.text((50, 15), keyword, fill=(0, 0, 0), font=font)

    return img


def _pil_to_clip(img: Image.Image) -> ImageClip:
    """PIL 이미지를 moviepy ImageClip으로 변환."""
    arr = np.array(img.convert("RGBA"))
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3].astype(float) / 255.0
    return ImageClip(rgb).set_mask(ImageClip(alpha, ismask=True))


def _make_background_clip(duration: float) -> ImageClip:
    """배경 클립 생성."""
    bg = make_background()
    return ImageClip(np.array(bg)).set_duration(duration)


def _progress_bar_clip(duration: float) -> VideoClip:
    """진행바 생성 (매 프레임 업데이트)."""
    def make_frame(t):
        progress = t / duration if duration > 0 else 0
        bar_width = int(WIDTH * progress)

        frame = Image.new("RGB", (WIDTH, 8), (15, 23, 42))
        draw = ImageDraw.Draw(frame)
        if bar_width > 0:
            draw.rectangle([(0, 0), (bar_width, 8)], fill=(56, 189, 248))

        return np.array(frame)

    return VideoClip(make_frame, duration=duration).set_position((0, HEIGHT - 8))


async def render_video(
    audio_path: Path,
    output_path: Path,
    ticker: str,
    topic: str,
    date_str: str,
    timeline: list,
) -> Path:
    """영상 렌더링 (비동기 래퍼).

    Args:
        audio_path: 나레이션 MP3 파일
        output_path: 출력 MP4 파일
        ticker: 종목코드
        topic: 영상 주제
        date_str: 방송 날짜
        timeline: 타이밍 정보
            [{"keyword": "...", "text": "...", "start": 0.0, "duration": 5.0}, ...]

    Returns:
        생성된 MP4 파일 경로
    """
    settings = get_settings()

    # moviepy 블로킹 작업을 별도 스레드에서 실행
    return await asyncio.to_thread(
        _render_video_sync,
        audio_path,
        output_path,
        ticker,
        topic,
        date_str,
        timeline,
        settings,
    )


def _render_video_sync(
    audio_path: Path,
    output_path: Path,
    ticker: str,
    topic: str,
    date_str: str,
    timeline: list,
    settings,
) -> Path:
    """실제 렌더링 (동기 구현)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. 오디오 로드
    audio = AudioFileClip(str(audio_path))
    total_duration = INTRO_SEC + audio.duration + OUTRO_SEC

    # 2. 레이어 구성
    layers = []

    # 배경
    layers.append(_make_background_clip(total_duration))

    # 타이틀 카드
    layers.append(
        _pil_to_clip(make_title_card(ticker, topic, date_str))
        .set_start(0)
        .set_duration(INTRO_SEC)
        .crossfadein(0.3)
        .crossfadeout(0.3)
    )

    # 타임라인 요소들 (offset 적용)
    for seg in timeline:
        start = INTRO_SEC + seg.get("start", 0)
        duration = seg.get("duration", 2.0)
        keyword = seg.get("keyword", "")
        text = seg.get("text", "")

        # 키워드 라벨
        if keyword:
            layers.append(
                _pil_to_clip(make_keyword_label(keyword))
                .set_start(start)
                .set_duration(duration)
                .set_position(("center", 200))
                .crossfadein(0.2)
                .crossfadeout(0.2)
            )

        # 자막
        if text:
            layers.append(
                _pil_to_clip(make_subtitle(text))
                .set_start(start)
                .set_duration(duration)
                .set_position(("center", HEIGHT - 150))
            )

    # 진행바
    layers.append(_progress_bar_clip(total_duration))

    # 3. 비디오 합성
    video = (
        CompositeVideoClip(layers, size=(WIDTH, HEIGHT))
        .set_duration(total_duration)
    )

    # 오디오 offset 적용
    audio_composite = CompositeAudioClip([audio.set_start(INTRO_SEC)])
    video = video.set_audio(audio_composite)

    # fps 직접 설정 (moviepy 호환성 문제 우회)
    video.fps = settings.video_fps

    # 4. 파일로 저장
    print(f"🎬 영상 렌더링 중: {output_path}")
    video.write_videofile(
        str(output_path),
        fps=settings.video_fps,
        codec=settings.video_codec,
        audio_codec="aac",
        threads=4,
        preset=settings.video_preset,
        logger=None,  # moviepy 로깅 비활성화
    )

    video.close()
    audio.close()

    return output_path
