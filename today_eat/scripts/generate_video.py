"""
Generate today's short from content list.

Reads from content.csv and generates a short video using edge-tts.
Output: video_id (for upload_video.py)
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
ASSETS_DIR = ROOT / "assets"
CONTENT_FILE = ROOT / "content.csv"
LOG_FILE = ROOT / "used_log.csv"

OUTPUT_DIR.mkdir(exist_ok=True)

def load_used_content():
    """Load previously used content IDs from log."""
    if not LOG_FILE.exists():
        return set()

    used = set()
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader:
            for row in reader:
                if row.get('content_id'):
                    used.add(row['content_id'])
    return used

def load_content():
    """Load unused content from CSV."""
    if not CONTENT_FILE.exists():
        print("❌ Error: content.csv not found")
        print(f"Create {CONTENT_FILE} with columns: content_id, text, tags")
        sys.exit(1)

    used = load_used_content()
    content_list = []

    with open(CONTENT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('content_id') not in used:
                content_list.append(row)

    if not content_list:
        print("⚠️ Warning: No unused content available")
        print("Please add new content to content.csv")
        sys.exit(1)

    return content_list[0]  # Use first unused content

def create_image_with_text(text, output_path):
    """Create image with text using Pillow."""
    img = Image.new('RGB', (1080, 1920), color='#1a1a1a')
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 80)
    except:
        font = ImageFont.load_default()

    lines = text.split('\n')
    y = 400
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        width = bbox[2] - bbox[0]
        x = (1080 - width) // 2
        draw.text((x, y), line, fill='white', font=font)
        y += 150

    img.save(output_path)

def generate_video(content_id, text):
    """Generate short video with TTS."""
    video_id = content_id

    image_path = OUTPUT_DIR / f"{video_id}_image.png"
    audio_path = OUTPUT_DIR / f"{video_id}_audio.mp3"
    video_path = OUTPUT_DIR / f"{video_id}.mp4"

    create_image_with_text(text, image_path)

    try:
        subprocess.run([
            "edge-tts",
            "--text", text,
            "--voice", "ko-KR-InJoonNeural",
            "--rate", "0",
            "--output-file", str(audio_path)
        ], check=True)
    except:
        print("⚠️ Warning: TTS failed, using silent video")
        audio_path = None

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-c:v", "libx264",
        "-t", "10",
        "-pix_fmt", "yuv420p",
    ]

    if audio_path and audio_path.exists():
        ffmpeg_cmd.extend(["-i", str(audio_path), "-c:a", "aac"])

    ffmpeg_cmd.extend(["-shortest", str(video_path)])

    subprocess.run(ffmpeg_cmd, check=True, capture_output=True)

    save_metadata(video_id, content_id, text)
    log_usage(content_id, text)

    return video_id

def save_metadata(video_id, content_id, text):
    """Save video metadata."""
    metadata = {
        "video_id": video_id,
        "content_id": content_id,
        "text": text,
        "created_at": datetime.now().isoformat(),
        "title": f"오늘 뭐 먹지? #{content_id}",
        "description": f"🍜 오늘의 음식 추천\n\n{text}\n\n#음식 #추천 #오늘뭐먹지",
        "tags": ["음식", "추천", "쇼츠"],
        "category_id": "26"
    }

    meta_path = OUTPUT_DIR / f"{video_id}.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')

def log_usage(content_id, text):
    """Log used content."""
    log_path = ROOT / "used_log.csv"

    exists = log_path.exists()
    with open(log_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(['content_id', 'text', 'used_at'])
        writer.writerow([content_id, text, datetime.now().isoformat()])

if __name__ == '__main__':
    content = load_content()
    video_id = generate_video(content['content_id'], content['text'])
    print(video_id)
