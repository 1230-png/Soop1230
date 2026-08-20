#!/usr/bin/env python3
"""
제품 리뷰 → 비디오 생성

흐름:
1. 제품 이미지 다운로드
2. 리뷰 텍스트를 음성으로 변환 (ElevenLabs)
3. 배경음악 추가
4. 최종 영상 (Shorts + 롱폼)
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import requests
import io
from PIL import Image, ImageDraw, ImageFont

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

OUTPUT_DIR = Path(__file__).parent.parent / "output"
ASSETS_DIR = Path(__file__).parent.parent / "assets"

OUTPUT_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)


def download_product_image(image_url: str, product_id: str) -> str:
    """
    제품 이미지 다운로드
    """
    image_path = ASSETS_DIR / f"{product_id}_product.jpg"

    if image_path.exists():
        return str(image_path)

    try:
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        img = Image.open(io.BytesIO(response.content))
        img = img.convert("RGB")

        # 정사각형으로 크롭 (Shorts 최적화)
        min_size = min(img.width, img.height)
        left = (img.width - min_size) // 2
        top = (img.height - min_size) // 2
        img = img.crop((left, top, left + min_size, top + min_size))

        img.save(image_path, quality=95)
        print(f"✅ 제품 이미지 다운로드: {image_path}", file=sys.stderr)
        return str(image_path)

    except Exception as e:
        print(f"⚠️ 이미지 다운로드 실패: {e} (폴백 생성)", file=sys.stderr)
        return create_fallback_product_image(product_id)


def create_fallback_product_image(product_id: str) -> str:
    """
    폴백: 제품 플레이스홀더 생성
    """
    image_path = ASSETS_DIR / f"{product_id}_fallback.jpg"

    img = Image.new("RGB", (1080, 1080), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", size=60)
    except:
        font = ImageFont.load_default()

    text = "Product"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (1080 - text_width) // 2
    y = 450

    draw.text((x, y), text, font=font, fill=(100, 100, 100))

    img.save(image_path, quality=95)
    return str(image_path)


def text_to_speech(text: str, product_id: str) -> str:
    """
    리뷰 텍스트를 음성으로 변환
    """
    if not ELEVENLABS_API_KEY:
        return None

    audio_path = OUTPUT_DIR / f"{product_id}_audio.mp3"

    if audio_path.exists():
        return str(audio_path)

    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    data = {
        "text": text,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    try:
        response = requests.post(
            "https://api.elevenlabs.io/v1/text-to-speech/Josh",  # 남성 음성
            headers=headers,
            json=data,
            timeout=60,
        )
        response.raise_for_status()

        with open(audio_path, "wb") as f:
            f.write(response.content)

        print(f"✅ 음성 생성: {audio_path}", file=sys.stderr)
        return str(audio_path)

    except Exception as e:
        print(f"⚠️ 음성 생성 실패: {e}", file=sys.stderr)
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
        return 120


def create_review_video(
    product_name: str,
    rating: float,
    image_path: str,
    audio_path: str,
    product_id: str,
    format_type: str = "short",  # 'short' (45s) or 'long' (2m)
) -> str:
    """
    제품 이미지 + 음성 → 최종 영상
    """
    output_video = OUTPUT_DIR / f"{product_id}_{format_type}.mp4"

    # 영상 길이 결정
    if format_type == "short":
        video_duration = 45
        width, height = 1080, 1920
    else:
        if audio_path:
            video_duration = min(get_audio_duration(audio_path), 120)
        else:
            video_duration = 60
        width, height = 1280, 720

    # 텍스트 오버레이 준비
    rating_text = f"⭐ {rating}/5.0 - {product_name[:20]}"

    # 이미지를 영상으로 변환 (zoom 효과)
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
        (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"drawtext=text='{rating_text}':fontfile=/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc:"
            f"fontsize=40:fontcolor=white:borderw=2:bordercolor=black:"
            f"x=(w-text_w)/2:y=h-80"
        ),
        "-pix_fmt",
        "yuv420p",
        "-y",
        str(output_video),
    ]

    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, timeout=60)

        # 음성 추가
        if audio_path and Path(audio_path).exists():
            final_output = OUTPUT_DIR / f"{product_id}_{format_type}_final.mp4"
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
            output_video.unlink()
            output_video = final_output

        print(f"✅ 영상 생성: {output_video}", file=sys.stderr)
        return str(output_video)

    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 실패: {e.stderr.decode()}", file=sys.stderr)
        return None


def main():
    """메인 프로세스"""
    reviews_json = sys.stdin.read()
    reviews_data = json.loads(reviews_json)

    reviews = reviews_data["reviews"]
    results = []

    for review in reviews:
        product_id = review.get("product_id", "unknown")
        product_name = review.get("product_name", "Product")
        rating = review.get("rating", 4.0)
        image_url = review.get("image_url", "")

        print(f"🎬 영상 생성: {product_name[:30]}...", file=sys.stderr)

        # 1단계: 이미지 다운로드
        image_path = download_product_image(image_url, product_id)
        if not image_path:
            print(f"⚠️ {product_id} 스킵", file=sys.stderr)
            continue

        # 2단계: 음성 생성
        # 리뷰 텍스트 조합
        review_text = f"{product_name}. 평점 {rating}점. {review.get('verdict', 'Good product.')}"
        audio_path = text_to_speech(review_text, product_id)

        # 3단계: Shorts 영상 생성
        shorts_video = create_review_video(
            product_name=product_name,
            rating=rating,
            image_path=image_path,
            audio_path=None,  # Shorts는 음성 없음
            product_id=product_id,
            format_type="short",
        )

        # 4단계: 롱폼 영상 생성 (음성 포함)
        long_video = None
        if audio_path:
            long_video = create_review_video(
                product_name=product_name,
                rating=rating,
                image_path=image_path,
                audio_path=audio_path,
                product_id=product_id,
                format_type="long",
            )

        if shorts_video:
            results.append(
                {
                    "product_id": product_id,
                    "product_name": product_name,
                    "rating": rating,
                    "shorts_video": shorts_video,
                    "long_video": long_video,
                    "pros": review.get("pros", []),
                    "cons": review.get("cons", []),
                    "price": review.get("product_price", 0),
                    "amazon_link": review.get("amazon_affiliate_link", ""),
                    "coupang_link": review.get("coupang_affiliate_link", ""),
                }
            )

    output = {
        "date": reviews_data["date"],
        "category": reviews_data["category"],
        "generated_videos": len(results),
        "videos": results,
    }

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
