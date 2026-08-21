"""Generate one '매일 영어 한마디' short: an English expression + Korean meaning
+ example, narrated (EN/KO/EN) with natural neural voices and muxed into a
vertical mp4, then upload to YouTube with Coupang Partners affiliate link.

Stack: Pillow (image/text), Google Cloud Text-to-Speech (neural TTS, 1M chars/month free),
ffmpeg (mux), YouTube Data API (upload).
"""

import csv
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import ImageDraw, ImageFont

import common

ROOT = Path(__file__).resolve().parent.parent
PHRASE_BANK = ROOT / "scripts" / "phrase_bank.json"
USED_LOG = ROOT / "used_log.csv"
OUTPUT_DIR = ROOT / "output"

WIDTH, HEIGHT = common.WIDTH, common.HEIGHT


def load_used_ids() -> set:
    if not USED_LOG.exists():
        return set()
    with open(USED_LOG, newline="", encoding="utf-8") as f:
        return {row["phrase_id"] for row in csv.DictReader(f)}


def pick_next_phrase() -> dict:
    bank = json.loads(PHRASE_BANK.read_text(encoding="utf-8"))
    used = load_used_ids()
    for item in bank:
        if item["id"] not in used:
            return item
    # Full cycle done — start reusing from the top rather than stalling forever.
    return bank[0]


def draw_content(img, phrase: dict, font_path: str) -> None:
    draw = ImageDraw.Draw(img)

    label_font = ImageFont.truetype(font_path, 42)
    phrase_font = ImageFont.truetype(font_path, 78)
    meaning_font = ImageFont.truetype(font_path, 52)
    example_font = ImageFont.truetype(font_path, 36)
    brand_font = ImageFont.truetype(font_path, 34)

    y = 620
    y = common.draw_centered(draw, "오늘의 표현", label_font, y, (150, 220, 210), wrap_width=20)
    y += 40

    y = common.draw_centered(draw, phrase["phrase_en"], phrase_font, y, (255, 255, 255), wrap_width=14)
    y += 30

    y = common.draw_centered(draw, phrase["meaning_ko"], meaning_font, y, (210, 235, 230), wrap_width=13)
    y += 90

    y = common.draw_centered(draw, phrase["example_en"], example_font, y, (235, 235, 235), wrap_width=28)
    y += 10
    y = common.draw_centered(draw, phrase["example_ko"], example_font, y, (180, 200, 195), wrap_width=22)

    brand = "매일 영어 한마디 · @200-y3b"
    bbox = draw.textbbox((0, 0), brand, font=brand_font)
    bx = (WIDTH - (bbox[2] - bbox[0])) / 2
    draw.text((bx, HEIGHT - 140), brand, font=brand_font, fill=(255, 255, 255))


def build_metadata(phrase: dict, video_id: str) -> dict:
    title = f"\"{phrase['phrase_en']}\" 무슨 뜻일까? | 매일 영어 한마디"
    description = (
        f"오늘의 표현: {phrase['phrase_en']}\n"
        f"뜻: {phrase['meaning_ko']}\n\n"
        f"예문: {phrase['example_en']}\n"
        f"해석: {phrase['example_ko']}\n\n"
        "매일 영어 한마디 — 실생활에서 바로 쓰는 영어 표현을 매일 전해드립니다.\n"
        "#영어공부 #영어회화 #매일영어한마디 #dailyenglish #영어표현 #shorts"
    )
    tags = [
        "영어공부", "영어회화", "매일영어한마디", "영어표현", "생활영어",
        "english expressions", "daily english", "learn english", "korean english",
        "shorts",
    ]
    return {
        "video_id": video_id,
        "title": title,
        "description": description,
        "tags": tags,
        "category_id": "27",  # Education
    }


def append_log(row: dict) -> None:
    is_new = not USED_LOG.exists()
    with open(USED_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    font_path = common.find_korean_font()

    phrase = pick_next_phrase()
    date_str = datetime.date.today().isoformat()
    video_id = f"{date_str}_{phrase['id']}"

    bg_path = OUTPUT_DIR / f"{video_id}.png"
    audio_path = OUTPUT_DIR / f"{video_id}.mp3"
    video_path = OUTPUT_DIR / f"{video_id}.mp4"
    meta_path = OUTPUT_DIR / f"{video_id}.json"

    top_color, bottom_color = common.pick_palette(phrase["id"])
    img = common.make_background(top_color, bottom_color)
    draw_content(img, phrase, font_path)
    img.save(bg_path)

    common.synthesize_narration(
        [
            ("en", phrase["phrase_en"]),
            ("ko", phrase["meaning_ko"]),
            ("en", phrase["phrase_en"]),
            ("en", phrase["example_en"]),
        ],
        audio_path,
        use_elevenlabs_for_en=True,  # Shorts get the higher-quality voice
    )
    common.mux_video(bg_path, audio_path, video_path)

    metadata = build_metadata(phrase, video_id)
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    append_log({
        "date": date_str,
        "phrase_id": phrase["id"],
        "phrase_en": phrase["phrase_en"],
        "meaning_ko": phrase["meaning_ko"],
        "video_title": metadata["title"],
        "video_file": str(video_path.relative_to(ROOT)),
        "youtube_video_id": "",
        "status": "generated",
    })

    try:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        subprocess.run(
            [
                sys.executable, "-m", "upload_video",
                str(video_path),
                "--title", metadata["title"],
                "--description", metadata["description"],
                "--log-file", str(USED_LOG),
            ],
            cwd=ROOT / "scripts",
            check=True,
            env=env,
        )
        print(f"✅ Uploaded {video_path}", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"❌ Upload failed: {e}", file=sys.stderr)
        raise

    print(video_id)  # sole stdout line


if __name__ == "__main__":
    sys.exit(main())
