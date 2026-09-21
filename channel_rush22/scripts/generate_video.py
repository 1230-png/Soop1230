"""Generate and publish one '머니러시' Short for @Rush22.

One item from content_bank.json becomes a three-scene vertical video:

    hook   — the 2-3 second question that stops the scroll
    body   — the actual explanation
    punch  — the takeaway plus a subscribe cue

Each scene is its own still + narration, muxed separately and concatenated,
so the frame changes as the video plays instead of holding one static card
for the whole runtime.

Stack: Pillow, edge-tts, ffmpeg, YouTube Data API. No paid service, no API
key beyond the YouTube OAuth credentials.

    python scripts/generate_video.py            # generate and upload
    python scripts/generate_video.py --dry-run  # generate only, no upload
"""

import argparse
import csv
import datetime
import json
import os
import sys
from pathlib import Path

from PIL import ImageDraw, ImageFont

import common

ROOT = Path(__file__).resolve().parent.parent
CONTENT_BANK = ROOT / "scripts" / "content_bank.json"
USED_LOG = ROOT / "used_log.csv"
# CI points this at the runner's temp dir so generated media never lands in
# the repo; local runs fall back to a gitignored folder.
OUTPUT_DIR = Path(os.environ.get("RUSH_OUTPUT_DIR", ROOT / "output"))

WIDTH, HEIGHT = common.WIDTH, common.HEIGHT

LOG_FIELDS = ["date", "content_id", "topic", "title", "youtube_video_id", "status"]


def load_used_ids() -> set:
    if not USED_LOG.exists():
        return set()
    with open(USED_LOG, newline="", encoding="utf-8") as f:
        return {row["content_id"] for row in csv.DictReader(f)}


def pick_next(bank) -> dict:
    used = load_used_ids()
    for item in bank:
        if item["id"] not in used:
            return item
    # Bank exhausted. Restart the cycle rather than failing the workflow —
    # a repeat beats a broken publishing streak, and the log makes it visible
    # that the bank needs topping up.
    print("⚠️  Content bank exhausted; restarting the cycle.", file=sys.stderr)
    return bank[0]


# --------------------------------------------------------------------------
# Scene rendering
# --------------------------------------------------------------------------

def render_hook(item, font_path):
    img = common.make_background("hook")
    draw = ImageDraw.Draw(img)
    badge_font = ImageFont.truetype(font_path, 40)
    text_font = ImageFont.truetype(font_path, 88)

    y = common.draw_badge(draw, item["topic"], badge_font, 380, common.ACCENT["hook"])
    body_h = common.measure_block(draw, item["hook"], text_font)
    start = max(y + 90, (common.SAFE_TOP + common.SAFE_BOTTOM - body_h) // 2)
    common.draw_block(draw, item["hook"], text_font, start, (255, 255, 255))

    common.draw_brand(draw, ImageFont.truetype(font_path, 34), "hook")
    return img


def render_body(item, font_path):
    img = common.make_background("body")
    draw = ImageDraw.Draw(img)
    badge_font = ImageFont.truetype(font_path, 40)
    text_font = ImageFont.truetype(font_path, 62)

    common.draw_badge(draw, item["topic"], badge_font, 380, common.ACCENT["body"])
    body_h = common.measure_block(draw, item["body"], text_font)
    start = max(560, (common.SAFE_TOP + common.SAFE_BOTTOM - body_h) // 2)
    common.draw_block(draw, item["body"], text_font, start, (240, 248, 246))

    common.draw_brand(draw, ImageFont.truetype(font_path, 34), "body")
    return img


def render_punch(item, font_path):
    img = common.make_background("punch")
    draw = ImageDraw.Draw(img)
    text_font = ImageFont.truetype(font_path, 80)
    cta_font = ImageFont.truetype(font_path, 44)

    body_h = common.measure_block(draw, item["punch"], text_font)
    start = max(common.SAFE_TOP + 120, (common.SAFE_TOP + common.SAFE_BOTTOM - body_h) // 2 - 80)
    y = common.draw_block(draw, item["punch"], text_font, start, (255, 255, 255))

    common.draw_badge(draw, "매일 한 편 · 구독", cta_font, y + 80, common.ACCENT["punch"])
    common.draw_brand(draw, ImageFont.truetype(font_path, 34), "punch")
    return img


SCENES = [
    ("hook", render_hook, "hook"),
    ("body", render_body, "body"),
    ("punch", render_punch, "punch"),
]


def build_video(item, font_path, video_key: str) -> Path:
    clips = []
    for kind, renderer, text_field in SCENES:
        stem = f"{video_key}_{kind}"
        img_path = OUTPUT_DIR / f"{stem}.png"
        audio_path = OUTPUT_DIR / f"{stem}.mp3"
        clip_path = OUTPUT_DIR / f"{stem}.mp4"

        renderer(item, font_path).save(img_path)
        # A beat of silence after each scene, longer on the last one so the
        # takeaway stays on screen and the loop back to the start is not abrupt.
        pause = 0.9 if kind == "punch" else 0.35
        common.narrate(item[text_field], audio_path, trailing_silence=pause)
        common.mux_scene(img_path, audio_path, clip_path)

        img_path.unlink()
        audio_path.unlink()
        clips.append(clip_path)

    final_path = OUTPUT_DIR / f"{video_key}.mp4"
    common.concat_scenes(clips, final_path)
    for clip in clips:
        clip.unlink()
    return final_path


# --------------------------------------------------------------------------
# Metadata
# --------------------------------------------------------------------------

def build_metadata(item) -> dict:
    # YouTube hard-limits titles to 100 characters; the hook plus the suffix
    # can exceed that on the longer items.
    suffix = " #shorts"
    hook = item["hook"]
    if len(hook) + len(suffix) > 100:
        hook = hook[: 100 - len(suffix)].rstrip()
    title = hook + suffix

    hashtags = " ".join(f"#{t.replace(' ', '')}" for t in item["tags"][:4])
    description = (
        f"{item['hook']}\n\n"
        f"{item['body']}\n\n"
        f"👉 {item['punch']}\n\n"
        "머니러시 — 하루 30초, 돈이 되는 생활경제 상식.\n"
        "매일 새 영상이 올라옵니다. 구독하고 놓치지 마세요.\n\n"
        f"{hashtags} #머니러시 #생활경제 #재테크 #shorts\n\n"
        "※ 이 영상은 일반적인 금융 상식을 소개하는 정보 제공용이며, "
        "특정 상품 투자 권유나 개별 상황에 대한 자문이 아닙니다."
    )
    tags = list(dict.fromkeys(item["tags"] + ["머니러시", "생활경제", "재테크", "경제상식", "shorts"]))
    return {"title": title, "description": description, "tags": tags}


def append_log(row: dict) -> None:
    is_new = not USED_LOG.exists()
    with open(USED_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run", action="store_true",
        help="render the video but skip the YouTube upload and the log entry",
    )
    parser.add_argument(
        "--id", help="render a specific content_bank id instead of the next unused one",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    font_path = common.find_korean_font()
    bank = json.loads(CONTENT_BANK.read_text(encoding="utf-8"))

    if args.id:
        item = next((i for i in bank if i["id"] == args.id), None)
        if item is None:
            raise SystemExit(f"No content_bank entry with id {args.id}")
    else:
        item = pick_next(bank)

    date_str = datetime.date.today().isoformat()
    video_key = f"{date_str}_{item['id']}"
    print(f"▶ {item['id']} — {item['topic']}")

    video_path = build_video(item, font_path, video_key)
    duration = common.probe_duration(video_path)
    print(f"✅ Rendered {video_path.name} ({duration:.1f}s)")

    if duration > 60:
        # Over 60s YouTube stops treating the upload as a Short, which changes
        # which feed it is served in. Worth failing loudly rather than
        # publishing into the wrong surface.
        print(
            f"❌ {duration:.1f}s exceeds the 60s Shorts limit — shorten this "
            f"entry's text in content_bank.json ({item['id']}).",
            file=sys.stderr,
        )
        return 1

    meta = build_metadata(item)

    if args.dry_run:
        print(f"\n[dry-run] title: {meta['title']}")
        print(f"[dry-run] kept at {video_path}")
        return 0

    import upload_video

    yt_id = upload_video.upload_short(
        video_path,
        title=meta["title"],
        description=meta["description"],
        tags=meta["tags"],
    )

    append_log({
        "date": date_str,
        "content_id": item["id"],
        "topic": item["topic"],
        "title": meta["title"],
        "youtube_video_id": yt_id,
        "status": "published",
    })
    video_path.unlink(missing_ok=True)
    print(f"\n✨ Success! https://youtube.com/shorts/{yt_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
