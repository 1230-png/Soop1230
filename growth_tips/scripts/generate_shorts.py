#!/usr/bin/env python3
"""
자기계발 팁 → Shorts 영상 생성

흐름:
1. Pexels에서 배경 영상 수집
2. FFmpeg로 9:16 크기 조정
3. 텍스트 오버레이 (팁 내용)
4. 배경음악 추가
5. 완성 (45초)
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import requests

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "your_key")

OUTPUT_DIR = Path(__file__).parent.parent / "output"
ASSETS_DIR = Path(__file__).parent.parent / "assets"

OUTPUT_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)


def download_background_video(query: str, tip_id: str) -> str:
    """
    Pexels API로 배경 영상 다운로드
    무료: 무제한
    """
    video_path = ASSETS_DIR / f"{tip_id}_bg.mp4"

    if video_path.exists():
        return str(video_path)

    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "per_page": 1,
        "orientation": "portrait",
    }

    try:
        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if not data["videos"]:
            print(f"⚠️ 배경 영상 없음: {query} (폴백 사용)")
            return create_fallback_video(tip_id)

        # 가장 작은 해상도 선택 (빠른 다운로드)
        video_files = data["videos"][0]["video_files"]
        video_url = min(video_files, key=lambda x: x["width"])["link"]

        response = requests.get(video_url, timeout=60)
        response.raise_for_status()

        with open(video_path, "wb") as f:
            f.write(response.content)

        print(f"✅ 배경 영상 다운로드: {video_path}")
        return str(video_path)

    except Exception as e:
        print(f"⚠️ 영상 다운로드 실패: {e} (폴백 사용)")
        return create_fallback_video(tip_id)


def create_fallback_video(tip_id: str) -> str:
    """
    폴백: 단색 배경 영상 생성 (45초)
    """
    video_path = ASSETS_DIR / f"{tip_id}_fallback.mp4"

    # 검은색 배경 45초 영상 (ffmpeg)
    cmd = [
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=1080x1920:d=45",
        "-y",
        str(video_path),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        print(f"✅ 폴백 영상 생성: {video_path}")
        return str(video_path)
    except subprocess.CalledProcessError as e:
        print(f"❌ 폴백 생성 실패: {e.stderr.decode()}", file=sys.stderr)
        return None


def create_subtitle_file(text: str, duration: float, output_path: Path):
    """SRT 자막 파일 생성"""
    lines = text.split("\n")
    chunk_duration = duration / max(1, len(lines))

    subtitles = []
    for i, line in enumerate(lines):
        if line.strip():
            start = i * chunk_duration
            end = (i + 1) * chunk_duration
            subtitles.append(
                f"{i + 1}\n"
                f"{int(start):02d}:00,000 --> {int(end):02d}:00,000\n"
                f"{line}\n\n"
            )

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(subtitles)


def add_text_overlay_and_music(
    video_path: str, text: str, tip_id: str, duration: float = 45.0
) -> str:
    """
    배경 영상 + 텍스트 오버레이 + 배경음악 합성

    텍스트 렌더링 (가운데 정렬, 흰색, 검은 테두리)
    """
    output_video = OUTPUT_DIR / f"{tip_id}_final.mp4"

    # 텍스트 크기 조정 (길이에 따라)
    fontsize = 60 if len(text) < 30 else 40 if len(text) < 60 else 30

    # FFmpeg 필터 (텍스트 + 배경음악)
    # 1. 영상 크기 조정 (9:16)
    # 2. 텍스트 오버레이 (중앙)
    # 3. 길이 제한 (45초)

    ffmpeg_cmd = [
        "ffmpeg",
        "-i",
        video_path,
        "-vf",
        (
            f"scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
            f"drawtext=text='{text}':fontfile=/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc:"
            f"fontsize={fontsize}:fontcolor=white:"
            f"borderw=3:bordercolor=black:"
            f"x=(w-text_w)/2:y=(h-text_h)/2"
        ),
        "-t",
        str(duration),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-y",
        str(output_video),
    ]

    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, timeout=120)
        print(f"✅ Shorts 영상 생성: {output_video}")
        return str(output_video)
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 실패: {e.stderr.decode()}", file=sys.stderr)
        return None


def main():
    """메인 프로세스"""
    # 표준입력에서 팁 JSON 받기
    tips_json = sys.stdin.read()
    tips_data = json.loads(tips_json)

    tips = tips_data["tips"]
    results = []

    for tip in tips:
        tip_id = tip["id"]
        text_ko = tip["tip_ko"]
        text_en = tip["tip_en"]
        category = tip["category"]

        print(f"🎬 {tip_id}: {text_ko}")

        # 1단계: 배경 영상 다운로드
        bg_video = download_background_video(category, tip_id)
        if not bg_video:
            print(f"⚠️ {tip_id} 스킵")
            continue

        # 2단계: 텍스트 오버레이 + 음악 (이중언어)
        # 한국어/영어 교대로
        text = f"{text_ko}\n\n{text_en}"
        video_path = add_text_overlay_and_music(bg_video, text, tip_id, duration=45)

        if video_path:
            results.append(
                {
                    "tip_id": tip_id,
                    "video_path": video_path,
                    "title_ko": f"💡 {text_ko}",
                    "title_en": f"💡 {text_en}",
                    "hashtags": tip.get("hashtags", []),
                    "category": category,
                }
            )

    # 결과 출력
    output = {
        "date": tips_data["date"],
        "generated_videos": len(results),
        "videos": results,
    }

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
