"""Generate food content Shorts with ASMR sound effects and text overlay.

ASMR-based cooking videos with subtitles (no TTS).
"""

import asyncio
import csv
import datetime
import json
import os
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Import shared utilities
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared import common

ROOT = Path(__file__).resolve().parent.parent
FOOD_BANK = ROOT / "data" / "food_list.json"
USED_LOG = ROOT / "data" / "used_videos.csv"
OUTPUT_DIR = ROOT / "output" / "generated"
SOUNDS_DIR = ROOT / "assets" / "sounds"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SOUNDS_DIR.mkdir(parents=True, exist_ok=True)


def load_food_content():
    """Load food content from JSON"""
    with open(FOOD_BANK, "r", encoding="utf-8") as f:
        return json.load(f)


def get_used_ids():
    """Get set of already used food IDs"""
    if not USED_LOG.exists():
        return set()
    used = set()
    try:
        with open(USED_LOG, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                for row in reader:
                    if row.get("video_id"):
                        used.add(int(row["video_id"]))
    except:
        pass
    return used


def pick_unused_content():
    """Pick a random unused food content"""
    content = load_food_content()
    used = get_used_ids()
    available = [c for c in content if c["id"] not in used]

    if not available:
        print("[warn] 모든 콘텐츠를 사용했습니다. 리셋 후 다시 시작합니다.", file=sys.stderr)
        return random.choice(content)

    return random.choice(available)


def pick_asmr_sounds(food_type, count=3):
    """Pick random ASMR sounds matching food type

    Food types: 채소(vegetables), 고기(meat), 계란(egg), 불(fire), 기름(oil), 국물(soup)
    """
    if not SOUNDS_DIR.exists():
        print("[warn] sounds 폴더가 없습니다. 침묵으로 진행합니다.", file=sys.stderr)
        return []

    sound_files = list(SOUNDS_DIR.glob("*.mp3"))
    if not sound_files:
        print("[warn] 효과음 파일이 없습니다. 침묵으로 진행합니다.", file=sys.stderr)
        return []

    # Filter by sound category if possible
    food_type_lower = str(food_type).lower()
    filtered = [f for f in sound_files if food_type_lower in f.name.lower()]

    # If no matching sounds, use all
    candidates = filtered if filtered else sound_files

    # Pick random sounds
    return random.sample(candidates, min(count, len(candidates)))


def make_title_image(content):
    """Create title image with gradient background and Korean text"""
    top_color, bottom_color = common.pick_palette(str(content["id"]))
    img = common.make_background(top_color, bottom_color)
    draw = ImageDraw.Draw(img)

    font_path = common.find_korean_font()
    title_font = ImageFont.truetype(font_path, 80)
    subtitle_font = ImageFont.truetype(font_path, 50)

    y = 400
    y = common.draw_centered(
        draw,
        content["title"],
        title_font,
        y,
        fill=(255, 255, 255),
        wrap_width=15,
        line_gap=20,
    )

    # Add cooking method/ingredient info
    y = 1200
    extra_text = content.get("korean", "")
    if extra_text:
        common.draw_centered(
            draw,
            extra_text,
            subtitle_font,
            y,
            fill=(200, 220, 255),
            wrap_width=20,
            line_gap=15,
        )

    return img


def make_step_image(content, step_num, step_text):
    """Create step-by-step cooking image with text overlay"""
    top_color, bottom_color = common.pick_palette(str(content["id"]) + f"step{step_num}")
    img = common.make_background(bottom_color, top_color)
    draw = ImageDraw.Draw(img)

    font_path = common.find_korean_font()
    step_font = ImageFont.truetype(font_path, 40)
    text_font = ImageFont.truetype(font_path, 55)

    # Step number
    y = 300
    draw.text((100, y), f"Step {step_num}", font=step_font, fill=(255, 215, 0))

    # Step description
    y = 500
    common.draw_centered(
        draw,
        step_text,
        text_font,
        y,
        fill=(255, 255, 255),
        wrap_width=18,
        line_gap=25,
    )

    return img


def concat_audio_files(audio_paths, output_path):
    """Concatenate multiple audio files using ffmpeg"""
    if not audio_paths:
        # Create silent audio if no sounds
        common.generate_silence(5.0, output_path)
        return True

    import subprocess

    # Create concat list
    concat_list = OUTPUT_DIR / "audio_concat_list.txt"
    with open(concat_list, "w") as f:
        for audio_path in audio_paths:
            f.write(f"file '{audio_path}'\n")

    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(output_path),
        ], check=True, capture_output=True)

        concat_list.unlink(missing_ok=True)
        return True
    except Exception as e:
        print(f"[error] 오디오 합성 실패: {e}", file=sys.stderr)
        concat_list.unlink(missing_ok=True)
        return False


def generate_video(content, sound_paths):
    """Generate final video with images and audio"""
    import subprocess

    # Create images
    title_img = make_title_image(content)
    title_img_path = OUTPUT_DIR / f"title_{content['id']}.png"
    title_img.save(title_img_path)

    # Create step images (2-3 steps)
    steps = content.get("steps", ["재료 준비", "조리 진행", "완성"])[:3]
    step_paths = []

    for i, step_text in enumerate(steps, 1):
        step_img = make_step_image(content, i, step_text)
        step_path = OUTPUT_DIR / f"step_{content['id']}_{i}.png"
        step_img.save(step_path)
        step_paths.append(step_path)

    # Create concat list for images
    concat_list = OUTPUT_DIR / f"concat_{content['id']}.txt"
    image_list = [(title_img_path, 3)] + [(p, 3) for p in step_paths]

    with open(concat_list, "w") as f:
        for img_path, duration in image_list:
            f.write(f"file '{img_path}'\n")
            f.write(f"duration {duration}\n")

    # Generate video from images
    video_no_audio = OUTPUT_DIR / f"video_noaudio_{content['id']}.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1080:1920",
        "-c:v", "libx264",
        "-crf", "23",
        str(video_no_audio),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"[error] 비디오 생성 실패: {e}", file=sys.stderr)
        return None

    # Prepare audio
    audio_path = OUTPUT_DIR / f"audio_{content['id']}.mp3"

    if sound_paths:
        # Use ASMR sounds
        if not concat_audio_files(sound_paths, audio_path):
            common.generate_silence(9.0, audio_path)
    else:
        # Fallback to silence
        common.generate_silence(9.0, audio_path)

    # Mux video with audio
    final_video = OUTPUT_DIR / f"food_shorts_{content['id']}.mp4"

    mux_cmd = [
        "ffmpeg", "-y",
        "-i", str(video_no_audio),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        str(final_video),
    ]

    try:
        subprocess.run(mux_cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"[error] 오디오 합성 실패: {e}", file=sys.stderr)
        return video_no_audio

    # Cleanup temp files
    video_no_audio.unlink(missing_ok=True)
    concat_list.unlink(missing_ok=True)
    audio_path.unlink(missing_ok=True)
    title_img_path.unlink(missing_ok=True)
    for step_path in step_paths:
        step_path.unlink(missing_ok=True)

    return final_video


def log_usage(content, video_path):
    """Log video generation record"""
    if not USED_LOG.exists():
        with open(USED_LOG, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["timestamp", "video_id", "title", "status"],
            )
            writer.writeheader()

    with open(USED_LOG, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["timestamp", "video_id", "title", "status"],
        )
        writer.writerow({
            "timestamp": datetime.datetime.now().isoformat(),
            "video_id": content["id"],
            "title": content["title"],
            "status": "generated" if video_path else "failed",
        })


def make_metadata(content, video_path):
    """Create metadata JSON for YouTube upload"""
    hashtags = " ".join(content.get("tags", ["#요리", "#음식"]))

    description = f"""{content.get('description', '')}

🛒 추천 상품: {content.get('coupang_link', 'https://www.coupang.com')}

━━━━━━━━━━━━━━━━━━━━
📺 오늘뭐먹지? (@오늘뭐먹지-f2d)
맛있게 먹는 일상 영상 채널
구독 👉 https://youtube.com/@오늘뭐먹지-f2d
━━━━━━━━━━━━━━━━━━━━

#음식 #요리 #쿠팡 #ASMR {hashtags}
"""

    metadata = {
        "title": content["title"],
        "description": description,
        "tags": content.get("tags", []),
        "privacy_status": "public",
        "category_id": "26",  # Howto & Style
        "make_for_kids": False,
    }

    return metadata


async def main():
    """Main video generation pipeline"""
    content = pick_unused_content()

    print(f"[생성] {content['title']}", file=sys.stderr)

    # Pick ASMR sounds
    food_type = content.get("sound_type", "all")
    sound_paths = pick_asmr_sounds(food_type, count=3)
    print(f"[음향] {len(sound_paths)}개 효과음 선택됨", file=sys.stderr)

    # Generate video
    video_path = generate_video(content, sound_paths)

    if not video_path:
        print(f"[실패] 영상 생성 실패", file=sys.stderr)
        log_usage(content, None)
        return None

    print(f"[완료] {video_path}", file=sys.stderr)

    # Save metadata
    metadata = make_metadata(content, video_path)
    metadata_path = OUTPUT_DIR / f"metadata_{content['id']}.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Log usage
    log_usage(content, video_path)

    return {
        "video_path": str(video_path),
        "metadata_path": str(metadata_path),
        "content_id": content["id"],
    }


if __name__ == "__main__":
    result = asyncio.run(main())
    if result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)
    else:
        sys.exit(1)
