#!/usr/bin/env python3
"""
감성 이야기 → 음성 + 배경 영상 → 최종 비디오

흐름:
1. 이야기 본문을 음성으로 변환 (ElevenLabs)
2. Unsplash에서 배경 영상/이미지 수집
3. FFmpeg로 음성 + 배경 + 자막 합성
4. YouTube Shorts 형식 (1080x1920)
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont

# 환경변수
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "your_key")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "your_key")

OUTPUT_DIR = Path(__file__).parent.parent / "output"
ASSETS_DIR = Path(__file__).parent.parent / "assets"

OUTPUT_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)


def text_to_speech(text: str, story_id: str) -> str:
    """
    ElevenLabs API로 음성 생성
    무료: 100K 글자/월 (충분함)

    Returns: 음성 파일 경로
    """
    audio_path = OUTPUT_DIR / f"{story_id}_audio.mp3"

    if audio_path.exists():
        return str(audio_path)

    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    data = {
        "text": text,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    try:
        response = requests.post(
            "https://api.elevenlabs.io/v1/text-to-speech/Rachel",  # 기본 음성
            headers=headers,
            json=data,
            timeout=60,
        )
        response.raise_for_status()

        with open(audio_path, "wb") as f:
            f.write(response.content)

        print(f"✅ 음성 생성 완료: {audio_path}")
        return str(audio_path)

    except Exception as e:
        print(f"❌ 음성 생성 실패: {e}", file=sys.stderr)
        # Fallback: 더미 음성 (실제 구현 시 로컬 TTS 사용)
        return None


def fetch_background_image(query: str, story_id: str) -> str:
    """
    Unsplash API로 배경 이미지 수집
    무료: 무제한

    Returns: 이미지 경로
    """
    image_path = ASSETS_DIR / f"{story_id}_bg.jpg"

    if image_path.exists():
        return str(image_path)

    headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
    params = {"query": query, "w": 1080, "h": 1920, "fm": "jpg"}

    try:
        response = requests.get(
            "https://api.unsplash.com/photos/random",
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()

        with open(image_path, "wb") as f:
            f.write(response.content)

        print(f"✅ 배경 이미지 다운로드: {image_path}")
        return str(image_path)

    except Exception as e:
        print(f"⚠️ 이미지 다운로드 실패 (로컬 폴백): {e}")
        # Fallback: 단색 배경 생성
        return create_fallback_image(story_id)


def create_fallback_image(story_id: str) -> str:
    """단색 배경 이미지 생성 (Fallback)"""
    img_path = ASSETS_DIR / f"{story_id}_fallback.jpg"

    # 1080x1920 이미지 생성
    img = Image.new("RGB", (1080, 1920), color=(30, 30, 40))
    img.save(img_path)

    return str(img_path)


def get_audio_duration(audio_file: str) -> float:
    """FFprobe로 오디오 길이 확인 (초)"""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1:noprint_wrappers=1",
                audio_file,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 180  # 기본값 3분


def create_subtitled_video(
    image_path: str, audio_path: str, text: str, story_id: str
) -> str:
    """
    배경 이미지 + 음성 + 자막 → 최종 비디오

    Shorts 형식: 1080x1920, 최대 60초
    """
    output_video = OUTPUT_DIR / f"{story_id}_final.mp4"

    # 오디오 길이로 비디오 길이 결정 (최대 60초)
    audio_duration = get_audio_duration(audio_path)
    video_duration = min(audio_duration, 60)

    # 자막 파일 생성 (SRT 형식)
    subtitle_file = OUTPUT_DIR / f"{story_id}.srt"
    create_subtitle_file(text, video_duration, subtitle_file)

    # FFmpeg 명령
    ffmpeg_cmd = [
        "ffmpeg",
        "-loop",
        "1",
        "-i",
        image_path,
        "-i",
        audio_path,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-shortest",
        "-t",
        str(video_duration),
        "-vf",
        f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        str(output_video),
        "-y",
    ]

    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, timeout=120)
        print(f"✅ 비디오 생성 완료: {output_video}")
        return str(output_video)
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 실패: {e.stderr.decode()}", file=sys.stderr)
        sys.exit(1)


def create_subtitle_file(text: str, duration: float, output_path: Path):
    """SRT 자막 파일 생성"""
    # 텍스트를 약 10초마다 나누기
    words = text.split()
    chunk_size = max(1, len(words) // max(1, int(duration / 10)))

    subtitles = []
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i : i + chunk_size])
        start_time = i * chunk_size / len(words) * duration
        end_time = min((i + chunk_size) / len(words) * duration, duration)

        subtitles.append(
            f"{len(subtitles) + 1}\n"
            f"{int(start_time)}:00,000 --> {int(end_time)}:00,000\n"
            f"{chunk}\n\n"
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(subtitles)


def main():
    """메인 프로세스"""
    # 표준입력에서 이야기 JSON 받기
    story_json = sys.stdin.read()
    story = json.loads(story_json)

    story_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"📖 이야기 처리: {story['title']}")

    # 1단계: 음성 생성
    audio_path = text_to_speech(story["content"], story_id)
    if not audio_path:
        print("❌ 음성 생성 실패", file=sys.stderr)
        sys.exit(1)

    # 2단계: 배경 이미지 수집
    bg_image = fetch_background_image(story["tags"][0], story_id)

    # 3단계: 비디오 생성
    video_path = create_subtitled_video(bg_image, audio_path, story["content"], story_id)

    # 4단계: 결과 출력
    result = {
        "video_id": story_id,
        "video_path": video_path,
        "title": story["title"],
        "description": story["moral"],
        "tags": story["tags"],
    }

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
