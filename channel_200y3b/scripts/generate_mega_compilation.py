"""Generate an hour-long 'best of' compilation for 매일 영어 한마디, combining
the same expressions used across the daily Shorts and weekly long-form
videos into one long-form upload. Run on a monthly cadence (see
mega_compilation.yml) rather than weekly like the regular long-form —
the phrase bank is a fixed pool, not something that grows on its own, so
running this any more often would just re-cover the same ground.

Slides are rebuilt from phrase_bank.json (the source both other pipelines
draw from) rather than re-muxing old files, since generated video files are
never persisted between CI runs. Reuses generate_compilation.py's slide/
title-clip builders so the visual style matches the weekly video exactly.
A cursor into the phrase bank is carried between runs so consecutive mega
videos start from a different point rather than always opening the same way.
"""

import csv
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

import common
import generate_compilation as gc
from generate_compilation import format_timestamp

ROOT = Path(__file__).resolve().parent.parent
PHRASE_BANK = ROOT / "scripts" / "phrase_bank.json"
MEGA_LOG = ROOT / "used_log_mega.csv"
STATE_FILE = ROOT / "mega_state.json"
OUTPUT_DIR = Path(os.environ.get("SHORTS_OUTPUT_DIR", ROOT / "output"))

TARGET_SECONDS = 55 * 60  # aim for ~55 min of slides before intro/outro
MAX_SLIDES = 450  # hard safety cap so a duration-measurement bug can't run away
# One chapter per slide would run well past YouTube's 5000-char description
# limit on an hour-long video (~330 slides) — mark every Nth slide instead.
CHAPTER_INTERVAL = 8


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"volume": 0, "cursor": 0}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def append_log(rows: list) -> None:
    is_new = not MEGA_LOG.exists()
    with open(MEGA_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


def build_metadata(phrases: list, volume: int, video_id: str, minutes: int, chapters: list) -> dict:
    title = f"영어 표현 총정리 Vol.{volume} ({minutes}분) | 매일 영어 한마디"
    chapter_lines = "\n".join(f"{format_timestamp(t)} {label}" for t, label in chapters)
    description = (
        f"그동안 올렸던 표현 중 {len(phrases)}개를 한 번에 모았습니다.\n\n"
        f"{chapter_lines}\n\n"
        "매일 영어 한마디 — 실생활에서 바로 쓰는 영어 표현을 매일 전해드립니다.\n"
        "#영어공부 #영어회화 #매일영어한마디 #영어표현총정리 #dailyenglish"
    )
    tags = [
        "영어공부", "영어회화", "매일영어한마디", "영어표현총정리", "생활영어",
        "english expressions", "daily english", "learn english compilation",
    ]
    return {
        "video_id": video_id, "title": title, "description": description,
        "tags": tags, "category_id": "27",
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state()
    font_path = common.find_korean_font()
    bank = json.loads(PHRASE_BANK.read_text(encoding="utf-8"))
    volume = state["volume"] + 1
    date_str = datetime.date.today().isoformat()
    video_id = f"{date_str}_mega_vol{volume}"

    intro_path = gc.make_title_clip(
        ["지금까지 나온", "영어 표현 총정리"],
        "안녕하세요, 매일 영어 한마디입니다. 그동안 올렸던 표현들을 한 번에 모아봤어요. 편하게 틀어놓고 들어보세요.",
        font_path, OUTPUT_DIR, f"{video_id}_intro",
    )
    clip_paths = [intro_path]
    chapters = [(0.0, "인트로")]

    used_phrases = []
    total_seconds = common.clip_duration(intro_path)
    cursor = state["cursor"]
    slide_index = 0
    while total_seconds < TARGET_SECONDS and slide_index < MAX_SLIDES:
        phrase = bank[cursor % len(bank)]
        cursor += 1
        slide_index += 1
        clip_path = gc.make_slide_clip(phrase, slide_index, "?", font_path, OUTPUT_DIR)
        clip_paths.append(clip_path)
        if slide_index % CHAPTER_INTERVAL == 1:
            chapters.append((total_seconds, phrase["phrase_en"]))
        total_seconds += common.clip_duration(clip_path)
        used_phrases.append(phrase)

    outro_path = gc.make_title_clip(
        ["오늘도 수고하셨어요", "다음 총정리에서 만나요"],
        "여기까지 이번 총정리 영상이었습니다. 도움이 되셨다면 구독과 좋아요 부탁드려요. 다음 영상에서 또 만나요!",
        font_path, OUTPUT_DIR, f"{video_id}_outro",
    )
    clip_paths.append(outro_path)
    chapters.append((total_seconds, "마무리"))
    total_seconds += common.clip_duration(outro_path)

    video_path = OUTPUT_DIR / f"{video_id}.mp4"
    common.concat_videos(clip_paths, video_path)
    for p in clip_paths:
        p.unlink()

    thumb_path = OUTPUT_DIR / f"{video_id}_thumb.jpg"
    sample_phrases = [p["phrase_en"] for p in used_phrases[:3]]
    thumb_img = common.make_thumbnail("영어 표현 총정리", sample_phrases, font_path, common.PALETTES[0])
    thumb_img.convert("RGB").save(thumb_path, quality=90)

    minutes = round(total_seconds / 60)
    metadata = build_metadata(used_phrases, volume, video_id, minutes, chapters)
    metadata["thumbnail_file"] = os.path.relpath(thumb_path, ROOT)
    meta_path = OUTPUT_DIR / f"{video_id}.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    append_log([
        {
            "date": date_str, "phrase_id": p["id"], "phrase_en": p["phrase_en"],
            "volume": volume, "video_file": os.path.relpath(video_path, ROOT),
            "youtube_video_id": "", "status": "generated",
        }
        for p in used_phrases
    ])

    try:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        subprocess.run(
            [
                sys.executable, "-m", "upload_video",
                str(video_path),
                "--title", metadata["title"],
                "--description", metadata["description"],
                "--thumbnail", str(thumb_path),
                "--log-file", str(MEGA_LOG),
                "--playlist", "매일 영어 한마디 · 총정리",
            ],
            cwd=ROOT / "scripts",
            check=True,
            env=env,
        )
        print(f"Uploaded {video_path}", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Upload failed: {e}", file=sys.stderr)
        raise

    save_state({"volume": volume, "cursor": cursor % len(bank)})

    print(video_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
