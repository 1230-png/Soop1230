#!/usr/bin/env python3
"""
뉴스 요약 → 비디오 생성

흐름:
1. 뉴스 이미지 다운로드 (또는 배경 영상)
2. 텍스트 오버레이 (한국어 요약)
3. 음성 합성 (선택) - ElevenLabs
4. 최종 영상 (Shorts 또는 롱폼)
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

OUTPUT_DIR = Path(__file__).parent.parent / "output"
ASSETS_DIR = Path(__file__).parent.parent / "assets"

OUTPUT_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)


def download_article_image(image_url: str, summary_id: str) -> str:
    """
    뉴스 기사의 이미지 다운로드
    """
    image_path = ASSETS_DIR / f"{summary_id}_article.jpg"

    if image_path.exists():
        return str(image_path)

    try:
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        # 이미지 검증 및 크기 조정
        img = Image.open(io.BytesIO(response.content))
        img = img.convert("RGB")

        # 썸네일 크기로 조정
        img.thumbnail((1280, 720), Image.Resampling.LANCZOS)

        img.save(image_path, quality=95)
        print(f"✅ 뉴스 이미지 다운로드: {image_path}")
        return str(image_path)

    except Exception as e:
        print(f"⚠️ 이미지 다운로드 실패: {e}")
        return None


def create_news_thumbnail(title: str, category: str, summary_id: str) -> str:
    """
    뉴스 기사용 썸네일 생성
    """
    thumbnail_path = ASSETS_DIR / f"{summary_id}_thumb.jpg"

    # 배경 색상 (카테고리별)
    colors = {
        "ai": (0, 120, 215),  # 파란색
        "crypto": (255, 153, 0),  # 주황색
        "startup": (100, 200, 100),  # 녹색
        "tech": (200, 100, 200),  # 보라색
    }
    bg_color = colors.get(category, (50, 50, 50))

    img = Image.new("RGB", (1280, 720), color=bg_color)
    draw = ImageDraw.Draw(img)

    # 폰트
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", size=60)
        category_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", size=40
        )
    except:
        title_font = ImageFont.load_default()
        category_font = ImageFont.load_default()

    # 제목 (줄 바꿈 처리)
    title_lines = []
    words = title.split()
    current_line = ""
    for word in words:
        if len(current_line + word) > 20:
            title_lines.append(current_line)
            current_line = word
        else:
            current_line += word + " "
    if current_line:
        title_lines.append(current_line)

    # 제목 그리기
    y_offset = 100
    for line in title_lines[:3]:  # 최대 3줄
        bbox = draw.textbbox((0, 0), line, font=title_font)
        line_width = bbox[2] - bbox[0]
        x = (1280 - line_width) // 2

        # 테두리
        for adj_x in [-3, -1, 1, 3]:
            for adj_y in [-3, -1, 1, 3]:
                draw.text((x + adj_x, y_offset + adj_y), line, font=title_font, fill=(0, 0, 0))

        # 흰 텍스트
        draw.text((x, y_offset), line, font=title_font, fill=(255, 255, 255))
        y_offset += 70

    # 카테고리 태그
    category_text = f"#{category.upper()}"
    bbox = draw.textbbox((0, 0), category_text, font=category_font)
    cat_width = bbox[2] - bbox[0]
    cat_x = (1280 - cat_width) // 2
    draw.text((cat_x, 600), category_text, font=category_font, fill=(255, 255, 255))

    img.save(thumbnail_path, quality=95)
    print(f"✅ 썸네일 생성: {thumbnail_path}")
    return str(thumbnail_path)


def text_to_speech(text: str, summary_id: str) -> str:
    """
    ElevenLabs로 음성 생성 (선택)
    """
    if not ELEVENLABS_API_KEY:
        return None

    audio_path = OUTPUT_DIR / f"{summary_id}_audio.mp3"

    if audio_path.exists():
        return str(audio_path)

    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    data = {
        "text": text,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    try:
        response = requests.post(
            "https://api.elevenlabs.io/v1/text-to-speech/Rachel",
            headers=headers,
            json=data,
            timeout=60,
        )
        response.raise_for_status()

        with open(audio_path, "wb") as f:
            f.write(response.content)

        print(f"✅ 음성 생성: {audio_path}")
        return str(audio_path)

    except Exception as e:
        print(f"⚠️ 음성 생성 실패: {e}")
        return None


def get_audio_duration(audio_file: str) -> float:
    """오디오 길이 확인"""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                audio_file,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return float(result.stdout.strip())
    except:
        return 180


def create_news_video(
    image_path: str,
    title: str,
    summary: str,
    summary_id: str,
    audio_path: str = None,
    format_type: str = "short",  # 'short' (45s) or 'long' (3m)
) -> str:
    """
    이미지 + 텍스트 + 음성 → 최종 영상

    Args:
        format_type: 'short' (Shorts, 45초) or 'long' (일반 영상, 3분)
    """
    output_video = OUTPUT_DIR / f"{summary_id}_{format_type}.mp4"

    # 영상 길이 결정
    if format_type == "short":
        video_duration = 45
        width, height = 1080, 1920
    else:
        if audio_path:
            video_duration = min(get_audio_duration(audio_path), 180)
        else:
            video_duration = 120
        width, height = 1280, 720

    # 이미지를 영상으로 변환 (ffmpeg)
    ffmpeg_cmd = [
        "ffmpeg",
        "-loop",
        "1",
        "-i",
        image_path,
        "-c:v",
        "libx264",
        "-t",
        str(video_duration),
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-pix_fmt",
        "yuv420p",
        "-y",
        str(output_video),
    ]

    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, timeout=60)

        # 음성 추가
        if audio_path:
            final_output = OUTPUT_DIR / f"{summary_id}_{format_type}_final.mp4"
            audio_cmd = [
                "ffmpeg",
                "-i",
                str(output_video),
                "-i",
                audio_path,
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                "-y",
                str(final_output),
            ]
            subprocess.run(audio_cmd, check=True, capture_output=True, timeout=60)
            output_video.unlink()  # 원본 삭제
            output_video = final_output

        print(f"✅ 영상 생성: {output_video}")
        return str(output_video)

    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 실패: {e.stderr.decode()}", file=sys.stderr)
        return None


def main():
    """메인 프로세스"""
    summaries_json = sys.stdin.read()
    summaries_data = json.loads(summaries_json)

    summaries = summaries_data["summaries"]
    results = []

    for summary in summaries:
        summary_id = f"{summaries_data['date']}_{summaries_data['category']}_" \
                     f"{len(results):02d}"

        print(f"🎬 {summary_id}: {summary['title_ko'][:40]}...")

        # 1단계: 썸네일 생성
        thumbnail = create_news_thumbnail(
            summary["title_ko"], summaries_data["category"], summary_id
        )

        # 2단계: 음성 생성 (선택)
        audio_path = None
        if ELEVENLABS_API_KEY:
            audio_path = text_to_speech(summary["summary_long"], summary_id)

        # 3단계: Shorts 형식 영상 (45초)
        shorts_video = create_news_video(
            image_path=thumbnail,
            title=summary["title_ko"],
            summary=summary["summary_short"],
            summary_id=summary_id,
            audio_path=None,  # Shorts는 텍스트만
            format_type="short",
        )

        # 4단계: 롱폼 영상 (3분, 음성 포함)
        long_video = None
        if audio_path:
            long_video = create_news_video(
                image_path=thumbnail,
                title=summary["title_ko"],
                summary=summary["summary_long"],
                summary_id=summary_id,
                audio_path=audio_path,
                format_type="long",
            )

        if shorts_video:
            results.append(
                {
                    "summary_id": summary_id,
                    "title_ko": summary["title_ko"],
                    "shorts_video": shorts_video,
                    "long_video": long_video,
                    "hashtags": summary.get("hashtags", []),
                    "category": summaries_data["category"],
                    "original_url": summary.get("original_url", ""),
                    "importance": summary.get("importance", 3),
                }
            )

    output = {
        "date": summaries_data["date"],
        "category": summaries_data["category"],
        "generated_videos": len(results),
        "videos": results,
    }

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    import io

    main()
