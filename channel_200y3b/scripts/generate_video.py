"""Generate one 'One Line A Day' short: background image + Korean TTS narration
muxed into a vertical mp4, plus a metadata JSON for the uploader.

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
CONTENT_BANK = ROOT / "scripts" / "content_bank.json"
USED_LOG = ROOT / "used_log.csv"
OUTPUT_DIR = ROOT / "output"

WIDTH, HEIGHT = 1080, 1920

MOOD_PALETTES = {
    "위로": ((70, 90, 150), (30, 35, 70)),
    "동기부여": ((210, 130, 60), (90, 45, 20)),
    "새벽감성": ((25, 30, 70), (5, 5, 20)),
    "자기긍정": ((200, 110, 140), (70, 30, 55)),
}
DEFAULT_PALETTE = ((60, 60, 90), (20, 20, 35))

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
        return {row["quote_id"] for row in csv.DictReader(f)}


def pick_next_quote() -> dict:
    bank = json.loads(CONTENT_BANK.read_text(encoding="utf-8"))
    used = load_used_ids()
    for item in bank:
        if item["id"] not in used:
            return item
    # Full cycle done — start reusing from the top rather than stalling forever.
    return bank[0]


def make_background(mood: str) -> Image.Image:
    top, bottom = MOOD_PALETTES.get(mood, DEFAULT_PALETTE)
    img = Image.new("RGB", (WIDTH, HEIGHT), top)
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))
    return img


def draw_quote(img: Image.Image, text: str, font_path: str) -> None:
    draw = ImageDraw.Draw(img)
    font_size = 70
    font = ImageFont.truetype(font_path, font_size)
    wrapped = textwrap.fill(text, width=12)
    lines = wrapped.split("\n")

    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    total_height = sum(line_heights) + (len(lines) - 1) * 20
    y = (HEIGHT - total_height) / 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (WIDTH - line_w) / 2
        # soft shadow for readability, then the line itself
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 120))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += bbox[3] + 20

    brand_font = ImageFont.truetype(font_path, 36)
    brand = "하루 한마디 · @200-y3b"
    bbox = draw.textbbox((0, 0), brand, font=brand_font)
    bx = (WIDTH - (bbox[2] - bbox[0])) / 2
    draw.text((bx, HEIGHT - 140), brand, font=brand_font, fill=(255, 255, 255, 180))


def synthesize_narration(text: str, out_path: Path) -> None:
    gTTS(text=text, lang="ko").save(str(out_path))


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


def build_metadata(quote: dict, video_id: str) -> dict:
    title = f"{quote['text'][:28]}{'…' if len(quote['text']) > 28 else ''} | 하루 한마디"
    description = (
        f"{quote['text']}\n\n"
        "하루 한마디 — 매일 짧은 위로와 동기부여를 전하는 채널입니다.\n"
        "#하루한마디 #위로 #동기부여 #힐링 #shorts"
    )
    tags = ["하루한마디", "위로", "동기부여", "힐링", "shorts", "명언", quote["mood"]]
    return {
        "video_id": video_id,
        "title": title,
        "description": description,
        "tags": tags,
        "category_id": "22",
    }


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    font_path = find_korean_font()

    quote = pick_next_quote()
    date_str = datetime.date.today().isoformat()
    video_id = f"{date_str}_{quote['id']}"

    bg_path = OUTPUT_DIR / f"{video_id}.png"
    audio_path = OUTPUT_DIR / f"{video_id}.mp3"
    video_path = OUTPUT_DIR / f"{video_id}.mp4"
    meta_path = OUTPUT_DIR / f"{video_id}.json"

    img = make_background(quote["mood"])
    draw_quote(img, quote["text"], font_path)
    img.save(bg_path)

    synthesize_narration(quote["text"], audio_path)
    mux_video(bg_path, audio_path, video_path)

    metadata = build_metadata(quote, video_id)
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    append_log({
        "date": date_str,
        "quote_id": quote["id"],
        "text": quote["text"],
        "video_title": metadata["title"],
        "video_file": str(video_path.relative_to(ROOT)),
        "youtube_video_id": "",
        "status": "generated",
    })

    print(f"Generated {video_path}", file=sys.stderr)
    print(video_id)  # sole stdout line, captured by the workflow


if __name__ == "__main__":
    sys.exit(main())
