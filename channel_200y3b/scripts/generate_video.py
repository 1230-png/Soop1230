"""Generate one '매일 영어 한마디' short: an English expression + Korean meaning
+ example, narrated (EN/KO/EN) and muxed into a vertical mp4, plus a metadata
JSON for the uploader.

Pure open-source stack: Pillow (image/text), gTTS (free TTS, no API key),
ffmpeg (mux). No paid API calls anywhere in this script.
"""

import csv
import datetime
import json
import subprocess
import sys
import textwrap
from pathlib import Path

from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PHRASE_BANK = ROOT / "scripts" / "phrase_bank.json"
USED_LOG = ROOT / "used_log.csv"
OUTPUT_DIR = ROOT / "output"

WIDTH, HEIGHT = 1080, 1920

# Fixed navy -> teal gradient for consistent, recognizable channel branding.
TOP_COLOR = (18, 38, 68)
BOTTOM_COLOR = (10, 58, 56)

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]


def find_korean_font() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    raise SystemExit(
        "No Korean-capable font found. Install one, e.g.:\n"
        "  sudo apt-get install -y fonts-noto-cjk\n"
        "or fonts-nanum, then re-run."
    )


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


def make_background() -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), TOP_COLOR)
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(TOP_COLOR[0] + (BOTTOM_COLOR[0] - TOP_COLOR[0]) * t)
        g = int(TOP_COLOR[1] + (BOTTOM_COLOR[1] - TOP_COLOR[1]) * t)
        b = int(TOP_COLOR[2] + (BOTTOM_COLOR[2] - TOP_COLOR[2]) * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))
    return img


def draw_centered(draw, text, font, y, fill, wrap_width, line_gap=16):
    wrapped = textwrap.fill(text, width=wrap_width)
    lines = wrapped.split("\n")
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (WIDTH - line_w) / 2
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=fill)
        y += (bbox[3] - bbox[1]) + line_gap
    return y


def draw_content(img: Image.Image, phrase: dict, font_path: str) -> None:
    draw = ImageDraw.Draw(img)

    label_font = ImageFont.truetype(font_path, 42)
    phrase_font = ImageFont.truetype(font_path, 78)
    meaning_font = ImageFont.truetype(font_path, 52)
    example_font = ImageFont.truetype(font_path, 36)
    brand_font = ImageFont.truetype(font_path, 34)

    y = 620
    y = draw_centered(draw, "오늘의 표현", label_font, y, (150, 220, 210), wrap_width=20)
    y += 40

    y = draw_centered(draw, phrase["phrase_en"], phrase_font, y, (255, 255, 255), wrap_width=14)
    y += 30

    y = draw_centered(draw, phrase["meaning_ko"], meaning_font, y, (210, 235, 230), wrap_width=13)
    y += 90

    y = draw_centered(draw, phrase["example_en"], example_font, y, (235, 235, 235), wrap_width=28)
    y += 10
    y = draw_centered(draw, phrase["example_ko"], example_font, y, (180, 200, 195), wrap_width=22)

    brand = "매일 영어 한마디 · @200-y3b"
    bbox = draw.textbbox((0, 0), brand, font=brand_font)
    bx = (WIDTH - (bbox[2] - bbox[0])) / 2
    draw.text((bx, HEIGHT - 140), brand, font=brand_font, fill=(255, 255, 255))


def synthesize_narration(phrase: dict, out_path: Path) -> None:
    tmp_dir = out_path.parent
    segments = [
        ("en", phrase["phrase_en"]),
        ("ko", phrase["meaning_ko"]),
        ("en", phrase["phrase_en"]),
        ("en", phrase["example_en"]),
    ]
    seg_paths = []
    for i, (lang, text) in enumerate(segments):
        seg_path = tmp_dir / f"{out_path.stem}_seg{i}.mp3"
        gTTS(text=text, lang=lang).save(str(seg_path))
        seg_paths.append(seg_path)

    with open(out_path, "wb") as out_f:
        for seg_path in seg_paths:
            out_f.write(seg_path.read_bytes())
            seg_path.unlink()


def mux_video(image_path: Path, audio_path: Path, out_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image_path),
            "-i", str(audio_path),
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-af", "loudnorm=I=-14:TP=-1.0:LRA=11",
            "-shortest", "-vf", "fps=30",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )


def append_log(row: dict) -> None:
    is_new = not USED_LOG.exists()
    with open(USED_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if is_new:
            writer.writeheader()
        writer.writerow(row)


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


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    font_path = find_korean_font()

    phrase = pick_next_phrase()
    date_str = datetime.date.today().isoformat()
    video_id = f"{date_str}_{phrase['id']}"

    bg_path = OUTPUT_DIR / f"{video_id}.png"
    audio_path = OUTPUT_DIR / f"{video_id}.mp3"
    video_path = OUTPUT_DIR / f"{video_id}.mp4"
    meta_path = OUTPUT_DIR / f"{video_id}.json"

    img = make_background()
    draw_content(img, phrase, font_path)
    img.save(bg_path)

    synthesize_narration(phrase, audio_path)
    mux_video(bg_path, audio_path, video_path)

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

    print(f"Generated {video_path}", file=sys.stderr)
    print(video_id)  # sole stdout line, captured by the workflow


if __name__ == "__main__":
    sys.exit(main())
