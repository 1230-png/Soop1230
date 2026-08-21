"""Generate one weekly long-form compilation video for 매일 영어 한마디:
~30 phrases back-to-back (intro + numbered slides + outro), long enough for
YouTube ad breaks (targets 8+ minutes) and to give viewers something worth
sitting through, not just another Short.

Uses Google Cloud Text-to-Speech (1M chars/month free) for narration,
Pillow + ffmpeg for video, YouTube Data API for upload.
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
LONGFORM_LOG = ROOT / "used_log_longform.csv"
VOLUME_FILE = ROOT / "longform_volume.txt"
# Defaults to a repo-local folder for local runs; CI sets SHORTS_OUTPUT_DIR
# to the runner's temp directory so generated videos/audio never get
# committed to git.
OUTPUT_DIR = Path(os.environ.get("SHORTS_OUTPUT_DIR", ROOT / "output"))

BATCH_SIZE = 30
SLIDE_TRAILING_SILENCE = 2.0  # seconds of pause per slide for reading time


def load_used_ids() -> set:
    if not LONGFORM_LOG.exists():
        return set()
    with open(LONGFORM_LOG, newline="", encoding="utf-8") as f:
        return {row["phrase_id"] for row in csv.DictReader(f)}


def pick_batch() -> list:
    bank = json.loads(PHRASE_BANK.read_text(encoding="utf-8"))
    used = load_used_ids()
    unused = [p for p in bank if p["id"] not in used]
    batch = unused[:BATCH_SIZE]
    if len(batch) < BATCH_SIZE:
        # Not enough unused left — wrap around, topping up from the start
        # (skipping ones already in this batch to avoid same-run duplicates).
        batch_ids = {p["id"] for p in batch}
        for p in bank:
            if len(batch) >= BATCH_SIZE:
                break
            if p["id"] not in batch_ids:
                batch.append(p)
                batch_ids.add(p["id"])
    return batch


def next_volume() -> int:
    if not VOLUME_FILE.exists():
        return 1
    return int(VOLUME_FILE.read_text().strip() or "1")


def save_volume(vol: int) -> None:
    VOLUME_FILE.write_text(str(vol + 1))


def make_slide_clip(phrase: dict, index: int, total: int, font_path: str, out_dir: Path) -> Path:
    stem = f"slide_{index:02d}_{phrase['id']}"
    bg_path = out_dir / f"{stem}.png"
    audio_path = out_dir / f"{stem}.mp3"
    clip_path = out_dir / f"{stem}.mp4"

    top_color, bottom_color = common.pick_palette(phrase["id"])
    img = common.make_background(top_color, bottom_color)
    draw = ImageDraw.Draw(img)

    label_font = ImageFont.truetype(font_path, 40)
    phrase_font = ImageFont.truetype(font_path, 74)
    meaning_font = ImageFont.truetype(font_path, 50)
    example_font = ImageFont.truetype(font_path, 34)
    brand_font = ImageFont.truetype(font_path, 32)

    y = 560
    y = common.draw_centered(draw, f"표현 {index}/{total}", label_font, y, (150, 220, 210), wrap_width=20)
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
    bx = (common.WIDTH - (bbox[2] - bbox[0])) / 2
    draw.text((bx, common.HEIGHT - 140), brand, font=brand_font, fill=(255, 255, 255))

    img.save(bg_path)

    common.synthesize_narration(
        [
            ("en", phrase["phrase_en"]),
            ("ko", phrase["meaning_ko"]),
            ("en", phrase["phrase_en"]),
            ("en", phrase["example_en"]),
        ],
        audio_path,
        trailing_silence=SLIDE_TRAILING_SILENCE,
        use_elevenlabs_for_en=True,  # ElevenLabs for all languages
    )
    common.mux_video(bg_path, audio_path, clip_path)
    bg_path.unlink()
    audio_path.unlink()
    return clip_path


def make_title_clip(text_lines, narration_text, font_path: str, out_dir: Path, stem: str) -> Path:
    bg_path = out_dir / f"{stem}.png"
    audio_path = out_dir / f"{stem}.mp3"
    clip_path = out_dir / f"{stem}.mp4"

    top_color, bottom_color = common.PALETTES[0]
    img = common.make_background(top_color, bottom_color)
    draw = ImageDraw.Draw(img)

    title_font = ImageFont.truetype(font_path, 68)
    y = 780
    for line in text_lines:
        y = common.draw_centered(draw, line, title_font, y, (255, 255, 255), wrap_width=14)
        y += 20

    brand_font = ImageFont.truetype(font_path, 34)
    brand = "매일 영어 한마디 · @200-y3b"
    bbox = draw.textbbox((0, 0), brand, font=brand_font)
    bx = (common.WIDTH - (bbox[2] - bbox[0])) / 2
    draw.text((bx, common.HEIGHT - 140), brand, font=brand_font, fill=(255, 255, 255))

    img.save(bg_path)
    common.synthesize_narration([("ko", narration_text)], audio_path, trailing_silence=1.0)
    common.mux_video(bg_path, audio_path, clip_path)
    bg_path.unlink()
    audio_path.unlink()
    return clip_path


def append_log(rows: list) -> None:
    is_new = not LONGFORM_LOG.exists()
    with open(LONGFORM_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


def build_metadata(batch: list, volume: int, video_id: str) -> dict:
    title = f"실생활 영어 표현 {len(batch)}개 모음 Vol.{volume} | 매일 영어 한마디"
    phrase_lines = "\n".join(f"{i+1}. {p['phrase_en']} — {p['meaning_ko']}" for i, p in enumerate(batch))
    description = (
        f"이번 영상에서 배우는 표현 {len(batch)}개:\n\n"
        f"{phrase_lines}\n\n"
        "매일 영어 한마디 — 실생활에서 바로 쓰는 영어 표현을 매일 전해드립니다.\n"
        "매주 이번 주 표현을 모아 정리 영상으로 올려드려요.\n"
        "#영어공부 #영어회화 #매일영어한마디 #dailyenglish #영어표현모음"
    )
    tags = [
        "영어공부", "영어회화", "매일영어한마디", "영어표현모음", "생활영어",
        "english expressions", "daily english", "learn english", "korean english",
        "영어공부법", "영어회화모음",
    ]
    return {
        "video_id": video_id,
        "title": title,
        "description": description,
        "tags": tags,
        "category_id": "27",  # Education
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    font_path = common.find_korean_font()

    batch = pick_batch()
    volume = next_volume()
    date_str = datetime.date.today().isoformat()
    video_id = f"{date_str}_longform_vol{volume}"

    clip_paths = []
    clip_paths.append(make_title_clip(
        ["오늘 배우는", f"영어 표현 {len(batch)}개"],
        f"안녕하세요, 매일 영어 한마디입니다. 오늘은 실생활에서 자주 쓰는 표현 {len(batch)}개를 모아왔어요. 하나씩 같이 배워볼까요?",
        font_path, OUTPUT_DIR, f"{video_id}_intro",
    ))
    for i, phrase in enumerate(batch, start=1):
        clip_paths.append(make_slide_clip(phrase, i, len(batch), font_path, OUTPUT_DIR))
    clip_paths.append(make_title_clip(
        ["오늘 표현", "다 배우셨나요?"],
        "여기까지 오늘의 표현 모음이었습니다. 도움이 되셨다면 구독과 좋아요 부탁드려요. 다음 영상에서 또 만나요!",
        font_path, OUTPUT_DIR, f"{video_id}_outro",
    ))

    video_path = OUTPUT_DIR / f"{video_id}.mp4"
    common.concat_videos(clip_paths, video_path)
    for p in clip_paths:
        p.unlink()

    thumb_path = OUTPUT_DIR / f"{video_id}_thumb.jpg"
    sample_phrases = [p["phrase_en"] for p in batch[:3]]
    thumb_img = common.make_thumbnail(f"영어 표현 {len(batch)}개", sample_phrases, font_path, common.PALETTES[0])
    thumb_img.convert("RGB").save(thumb_path, quality=90)

    metadata = build_metadata(batch, volume, video_id)
    metadata["thumbnail_file"] = os.path.relpath(thumb_path, ROOT)
    meta_path = OUTPUT_DIR / f"{video_id}.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    append_log([
        {
            "date": date_str,
            "phrase_id": p["id"],
            "phrase_en": p["phrase_en"],
            "volume": volume,
            "video_file": os.path.relpath(video_path, ROOT),
            "youtube_video_id": "",
            "status": "generated",
        }
        for p in batch
    ])
    save_volume(volume)

    try:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        subprocess.run(
            [
                sys.executable, "-m", "upload_video",
                str(video_path),
                "--title", metadata["title"],
                "--description", metadata["description"],
                "--thumbnail", str(thumb_path),
                "--log-file", str(LONGFORM_LOG),
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
