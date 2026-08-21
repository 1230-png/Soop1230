"""Build one cooking ASMR Shorts from free stock footage.

Every scene is real moving video — knife work, a sizzling pan, sauce going
in — cut to length, filled to 9:16, graded, and captioned. Each step also
carries its own sound cue, so the bed changes with what is on screen.

There is no still-image path. If footage cannot be sourced for a scene the
run fails instead of publishing a slideshow; a static card is worse than no
upload, because it goes out under the channel's name.

Free sources only. sources.py handles provider order and caching; the three
optional API keys are all free-of-charge registrations, and Wikimedia
Commons needs no key at all.
"""

import csv
import datetime
import json
import random
import subprocess
import sys
from pathlib import Path

import asmr  # noqa: E402
import compose  # noqa: E402
import render  # noqa: E402
import sources  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FOOD_BANK = ROOT / "data" / "food_list.json"
USED_LOG = ROOT / "data" / "used_videos.csv"
OUTPUT_DIR = ROOT / "output" / "generated"
ASSETS_DIR = ROOT / "assets"
CLIPS_DIR = ASSETS_DIR / "clips"
SOUNDS_DIR = ASSETS_DIR / "sounds"
WORK_DIR = OUTPUT_DIR / ".work"

TITLE_SECONDS = 2.8
STEP_SECONDS = 3.4
CROSSFADE = 0.4

for folder in (OUTPUT_DIR, CLIPS_DIR, SOUNDS_DIR):
    folder.mkdir(parents=True, exist_ok=True)


def load_content():
    with open(FOOD_BANK, "r", encoding="utf-8") as f:
        return json.load(f)


def used_ids():
    if not USED_LOG.exists():
        return set()
    found = set()
    try:
        with open(USED_LOG, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                for row in reader:
                    raw = row.get("video_id", "")
                    if raw.isdigit():
                        found.add(int(raw))
    except OSError:
        pass
    return found


def pick_content():
    content = load_content()
    fresh = [c for c in content if c["id"] not in used_ids()]
    if not fresh:
        print("[info] 모든 콘텐츠를 사용했습니다. 처음부터 다시 사용합니다.", file=sys.stderr)
        fresh = content
    return random.choice(fresh)


def normalize_steps(content):
    """Accept {text, sound, ingredient, clip_query, sound_query} or a string."""
    fallback = content.get("sound_type", "")
    steps = []
    for raw in content.get("steps", []):
        if isinstance(raw, dict):
            steps.append({
                "text": raw.get("text", ""),
                "sound": raw.get("sound", fallback),
                "ingredient": raw.get("ingredient", ""),
                "clip_query": raw.get("clip_query", ""),
                "sound_query": raw.get("sound_query", ""),
            })
        else:
            steps.append({"text": str(raw), "sound": fallback,
                          "ingredient": "", "clip_query": "", "sound_query": ""})
    return [s for s in steps if s["text"]]


def local_clip(content_id, slot):
    """Footage the channel filmed itself always beats anything downloaded."""
    for ext in (".mp4", ".mov", ".webm", ".mkv"):
        candidate = CLIPS_DIR / f"{content_id}_{slot}{ext}"
        if candidate.exists():
            return candidate
    return None


def find_clip(content_id, slot, query):
    return local_clip(content_id, slot) or sources.fetch_video(query, ASSETS_DIR)


def local_sound(cues):
    """A recorded clip in assets/sounds/ whose name mentions one of the cues."""
    if not SOUNDS_DIR.exists():
        return None
    clips = [p for p in SOUNDS_DIR.iterdir()
             if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac"}]
    if not clips:
        return None
    names = asmr.parse_sound_types(cues)
    matched = [p for p in clips if any(n in p.name for n in names)]
    return random.choice(matched or clips)


def build_bed(scene, index, out_path, first, last, seed):
    """One scene's sound: recorded file, then a fetched clip, then synthesis.

    Only the first and last beds are faded — the joins between them are
    handled by acrossfade, and fading twice punches a hole at every cut.
    """
    recorded = local_sound(scene["sound"]) or sources.fetch_audio(
        scene.get("sound_query", ""), ASSETS_DIR
    )
    if recorded:
        filters = []
        if first:
            filters.append("afade=t=in:st=0:d=0.3")
        if last:
            filters.append(
                f"afade=t=out:st={max(0.0, scene['duration'] - 0.3):.2f}:d=0.3"
            )
        cmd = ["ffmpeg", "-y", "-v", "error",
               "-stream_loop", "-1", "-i", str(recorded),
               "-t", f"{scene['duration']:.2f}"]
        if filters:
            cmd += ["-af", ",".join(filters)]
        cmd += ["-c:a", "libmp3lame", "-b:a", "192k", str(out_path)]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            print(f"  [warn] 효과음 처리 실패, 합성으로 대체: {recorded.name}", file=sys.stderr)

    return asmr.synthesize_bed(
        scene["sound"], scene["duration"], out_path,
        fade_in=first, fade_out=last, seed=seed,
    )


def build(content, scenes):
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    clips, beds = [], []

    for i, scene in enumerate(scenes):
        overlay = WORK_DIR / f"overlay_{i}.png"
        scene["overlay"].save(overlay)

        clip = WORK_DIR / f"scene_{i}.mp4"
        ok = compose.make_scene(
            scene["clip"], overlay, scene["duration"], clip,
            seed=f"{content['id']}-{i}", speed=scene.get("speed", 1.0),
        )
        if not ok:
            print(f"[실패] STEP {i} 장면 합성 실패", file=sys.stderr)
            return None
        clips.append(clip)

        bed = WORK_DIR / f"bed_{i}.mp3"
        if build_bed(scene, i, bed, first=(i == 0),
                     last=(i == len(scenes) - 1), seed=f"{content['id']}-{i}"):
            beds.append(bed)

    silent = WORK_DIR / "silent.mp4"
    if not compose.concat(clips, silent, fade=CROSSFADE):
        return None

    final = OUTPUT_DIR / f"food_shorts_{content['id']}.mp4"
    audio = WORK_DIR / "audio.mp3"

    # Must match the video's xfade, or the sound slides off the step it
    # belongs to (see asmr.concat_beds).
    if beds and asmr.concat_beds(beds, audio, crossfade=CROSSFADE):
        if not compose.mux(silent, audio, final):
            silent.replace(final)
    else:
        silent.replace(final)

    _clean()
    return final


def _clean():
    if not WORK_DIR.exists():
        return
    for path in sorted(WORK_DIR.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    WORK_DIR.rmdir()


def log_usage(content, ok):
    new = not USED_LOG.exists()
    USED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(USED_LOG, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "video_id", "title", "status"])
        if new:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.datetime.now().isoformat(),
            "video_id": content["id"],
            "title": content["title"],
            "status": "generated" if ok else "failed",
        })


def metadata(content):
    tags = " ".join(content.get("tags", ["#요리", "#음식"]))
    return {
        "title": content["title"],
        "description": f"""{content.get('description', '')}

🛒 추천 상품: {content.get('coupang_link', 'https://www.coupang.com')}

━━━━━━━━━━━━━━━━━━━━
📺 오늘뭐먹지? (@오늘뭐먹지-f2d)
쉽고 맛있는 요리의 즐거움
구독 👉 https://youtube.com/@오늘뭐먹지-f2d
━━━━━━━━━━━━━━━━━━━━

영상·효과음: Pixabay / Pexels / Freesound / Wikimedia Commons (무료 라이선스)

#음식 #요리 #ASMR #쿠팡 {tags}
""",
        "tags": content.get("tags", []),
        "privacy_status": "public",
        "category_id": "26",
        "make_for_kids": False,
    }


def main():
    content = pick_content()
    steps = normalize_steps(content)
    total = len(steps)

    keys = sources.configured()
    print(f"[생성] {content['title']}", file=sys.stderr)
    print(f"[소스] 무료 키: {', '.join(keys) if keys else '없음 (Commons만 사용)'}",
          file=sys.stderr)

    print("  타이틀 영상 확보 중...", file=sys.stderr)
    title_clip = find_clip(content["id"], "title", content.get("clip_query", ""))
    if not title_clip:
        return _abort(content, "타이틀")

    scenes = [{
        "clip": title_clip,
        "overlay": render.title_overlay(content),
        "duration": TITLE_SECONDS,
        "sound": content.get("sound_type", "김"),
        "sound_query": content.get("sound_query", ""),
    }]

    for i, step in enumerate(steps, 1):
        print(f"  STEP {i} 영상 확보 중...", file=sys.stderr)
        clip = find_clip(content["id"], f"step{i}", step["clip_query"])
        if not clip:
            return _abort(content, f"STEP {i}")

        scenes.append({
            "clip": clip,
            "overlay": render.step_overlay(
                i, total, step["text"], step["ingredient"]
            ),
            "duration": STEP_SECONDS,
            "sound": step["sound"],
            "sound_query": step["sound_query"],
            # Slow the middle step slightly: the money shot in a food video is
            # almost always the pour or the sizzle, and it reads better under time.
            "speed": 0.75 if i == 2 else 1.0,
        })

    video = build(content, scenes)
    if not video:
        log_usage(content, False)
        return None

    print(f"[완료] {video}", file=sys.stderr)
    meta_path = OUTPUT_DIR / f"metadata_{content['id']}.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata(content), f, ensure_ascii=False, indent=2)

    log_usage(content, True)
    return {
        "video_path": str(video),
        "metadata_path": str(meta_path),
        "content_id": content["id"],
    }


def _abort(content, where):
    print(
        f"[실패] {where} 장면 영상을 구하지 못했습니다.\n"
        "  정지 이미지로 대체하지 않고 중단합니다.\n"
        "  · 무료 키를 등록하면 소스 폭이 넓어집니다 "
        "(PIXABAY_API_KEY / PEXELS_API_KEY)\n"
        "  · 직접 촬영본은 assets/clips/{id}_title.mp4 로 넣으면 최우선 사용됩니다\n"
        "  · data/food_list.json 의 clip_query 를 더 일반적인 단어로 바꿔보세요",
        file=sys.stderr,
    )
    log_usage(content, False)
    return None


if __name__ == "__main__":
    result = main()
    if not result:
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False))
