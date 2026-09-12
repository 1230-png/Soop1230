"""Build one long-form pack: pick phrases, synthesize, render cards, encode.

    python3 longform/build.py --pack weekly_review [--offline] [--limit N]

Output lands in longform/build/<date>-<pack>/ as video.mp4, metadata.json
and thumbnail.png. Nothing here touches the Shorts pipeline's files.
"""

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import cards, tts  # noqa: E402

ROOT = Path(__file__).resolve().parent
PACKS_FILE = ROOT / "packs.yaml"
PHRASES_FILE = ROOT / "data" / "phrases.json"
USED_FILE = ROOT / "data" / "used.json"
BUILD_ROOT = ROOT / "build"

# Steps that speak, and which voice/rate each uses. Everything not listed
# here is silence of some kind.
SPOKEN = {
    "en_normal": ("en", "voice_en", None),
    "en_slow": ("en", "voice_en_alt", "rate_slow"),
    "ko": ("ko", "voice_ko", None),
    "example_en": ("example", "voice_en", None),
    "example_ko": ("example", "voice_ko", None),
}
# Which line the card should light up for each step.
STAGE = {
    "en_normal": "en", "en_slow": "en", "ko": "ko",
    "example_en": "example", "example_ko": "example",
    "shadow_gap": "shadow",
}


def load_packs() -> dict:
    return yaml.safe_load(PACKS_FILE.read_text(encoding="utf-8"))


def load_phrases() -> list:
    if not PHRASES_FILE.exists():
        raise SystemExit(
            f"{PHRASES_FILE} not found. Build it first:\n"
            "  python3 longform/import_queue.py"
        )
    return json.loads(PHRASES_FILE.read_text(encoding="utf-8"))


def load_used() -> dict:
    if USED_FILE.exists():
        return json.loads(USED_FILE.read_text(encoding="utf-8"))
    return {"packs": {}, "topic_cursor": 0}


def save_used(state: dict) -> None:
    USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    USED_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")


def pick_phrases(phrases: list, pack_id: str, count: int, state: dict,
                 topic: str = "") -> list:
    """Unused-first selection, oldest-used as fallback.

    Recycling is per pack, so a phrase that appeared in a shadowing drill is
    still fresh for the monthly review — the two present it differently
    enough that a viewer would not read it as a repeat.
    """
    pool = [p for p in phrases if p.get("topic") == topic] if topic else list(phrases)
    if not pool:
        raise SystemExit(f"No phrases match topic {topic!r}")

    seen = state.get("packs", {}).get(pack_id, {})
    unused = [p for p in pool if p["id"] not in seen]
    picked = unused[:count]

    if len(picked) < count:
        # Oldest first, so recycling spreads evenly instead of hammering the
        # same handful every time the pool runs short.
        rest = sorted((p for p in pool if p["id"] in seen),
                      key=lambda p: seen[p["id"]])
        picked += rest[: count - len(picked)]

    if not picked:
        raise SystemExit(f"Could not select any phrase for pack {pack_id}")
    return picked


def fmt_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def build_segments(pack: dict, defaults: dict, picked: list, topic: str,
                   work: Path, offline: bool):
    """Expand intro + per-phrase recipe + outro into a flat segment list.

    Returns (segments, chapters, total_seconds) where each segment is
    {audio, seconds, card}.
    """
    segments, chapters = [], []
    total = 0.0
    count = len(picked)

    def add(audio: Path, card: Path):
        nonlocal total
        seconds = tts.duration_of(audio)
        segments.append({"audio": audio, "seconds": seconds, "card": card})
        total += seconds

    # Intro
    intro_card = cards.render_title(
        work / "card_intro.png",
        lines=[pack["name"]],
        subtitle=f"표현 {count}개",
    )
    add(tts.synthesize(pack["intro_ko"], defaults["voice_ko"], offline=offline),
        intro_card)
    chapters.append((0.0, "인트로"))

    card_cache: dict = {}

    def card_for(idx: int, phrase: dict, stage: str) -> Path:
        key = (phrase["id"], stage)
        if key not in card_cache:
            card_cache[key] = cards.render(
                work / f"card_{idx:03d}_{stage}.png",
                phrase=phrase, index=idx, total=count, stage=stage, topic=topic,
            )
        return card_cache[key]

    for idx, phrase in enumerate(picked, start=1):
        chapters.append((total, phrase["en"]))
        last_en_seconds = 0.0

        for step in pack["recipe"]:
            if step in SPOKEN:
                kind, voice_key, rate_key = SPOKEN[step]
                text = {
                    "en": phrase["en"],
                    "ko": phrase["ko"],
                    "example": phrase.get("ex_en" if step == "example_en" else "ex_ko", ""),
                }[kind]
                if not text:
                    continue  # phrase has no example; skip rather than emit silence
                rate = defaults[rate_key] if rate_key else "+0%"
                audio = tts.synthesize(text, defaults[voice_key], rate, offline=offline)
                if kind == "en" or step == "example_en":
                    last_en_seconds = tts.duration_of(audio)
                add(audio, card_for(idx, phrase, STAGE[step]))

            elif step == "shadow_gap":
                # The whole point: long enough to actually say it back.
                seconds = last_en_seconds + defaults["shadow_pad"]
                audio = tts.make_silence(
                    seconds, work / f"gap_{idx:03d}_{len(segments)}.mp3")
                add(audio, card_for(idx, phrase, "shadow"))

            elif step in ("gap_short", "gap_long"):
                seconds = defaults[step]
                audio = tts.make_silence(
                    seconds, work / f"gap_{idx:03d}_{len(segments)}.mp3")
                # Hold the last card rather than flashing a new one.
                add(audio, segments[-1]["card"] if segments else intro_card)

            else:
                raise SystemExit(f"Unknown recipe step: {step}")

    # Outro
    outro_card = cards.render_title(
        work / "card_outro.png",
        lines=["오늘도 수고하셨어요"],
        subtitle="구독하시면 다음 영상을 놓치지 않아요",
    )
    chapters.append((total, "마무리"))
    add(tts.synthesize(pack["outro_ko"], defaults["voice_ko"], offline=offline),
        outro_card)

    return segments, chapters, total


def encode(segments: list, out_dir: Path, work: Path, fps: int) -> Path:
    """Concat audio, concat stills, mux. Stills + copy audio keeps a
    70-minute encode down to a couple of minutes."""
    audio_list = work / "audio.txt"
    audio_list.write_text(
        "\n".join(f"file '{s['audio'].resolve()}'" for s in segments) + "\n",
        encoding="utf-8")
    audio_mix = work / "audio.m4a"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(audio_list),
         "-c:a", "aac", "-b:a", "128k", str(audio_mix)],
        check=True, capture_output=True)

    lines = []
    for s in segments:
        lines.append(f"file '{s['card'].resolve()}'")
        lines.append(f"duration {s['seconds']:.3f}")
    # The concat demuxer drops the final entry's duration, so the last image
    # has to be repeated without one or the closing card is cut off.
    lines.append(f"file '{segments[-1]['card'].resolve()}'")
    video_list = work / "video.txt"
    video_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out_path = out_dir / "video.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "concat", "-safe", "0", "-i", str(video_list),
         "-i", str(audio_mix),
         "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
         "-crf", "26", "-r", str(fps), "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-shortest", "-movflags", "+faststart",
         str(out_path)],
        check=True, capture_output=True)
    return out_path


def build_description(pack: dict, chapters: list, count: int, topic: str) -> str:
    head = f"{pack['name']} — 표현 {count}개"
    if topic:
        head += f" · {topic}"
    lines = [head, "", "타임스탬프"]
    lines += [f"{fmt_timestamp(t)} {label}" for t, label in chapters]
    lines += [
        "",
        "매일 영어 한마디 — 실생활에서 바로 쓰는 영어 표현을 매일 전해드립니다.",
        "매일 09시 / 15시 / 21시에 쇼츠를, 주말에는 모아듣기 영상을 올립니다.",
        "",
        "#영어공부 #영어회화 #매일영어한마디 #영어듣기 #dailyenglish",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a long-form pack")
    ap.add_argument("--pack", required=True)
    ap.add_argument("--offline", action="store_true",
                    help="Silence instead of TTS — pipeline test with no network")
    ap.add_argument("--limit", type=int,
                    help="Override the pack's phrase count (for quick tests)")
    args = ap.parse_args()

    config = load_packs()
    if args.pack not in config["packs"]:
        raise SystemExit(f"Unknown pack {args.pack!r}. "
                         f"Available: {', '.join(config['packs'])}")
    pack = config["packs"][args.pack]
    defaults = config["defaults"]

    phrases = load_phrases()
    state = load_used()

    topic = ""
    if args.pack == "situation_pack":
        topics = config["topics"]
        topic = topics[state.get("topic_cursor", 0) % len(topics)]

    count = args.limit or pack["phrase_count"]
    picked = pick_phrases(phrases, args.pack, count, state, topic)
    count = len(picked)

    date_str = datetime.date.today().isoformat()
    out_dir = BUILD_ROOT / f"{date_str}-{args.pack}"
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)

    print(f"[build] {args.pack}: {count} phrases"
          + (f", topic={topic}" if topic else "")
          + (" (offline)" if args.offline else ""), file=sys.stderr)

    segments, chapters, total = build_segments(
        pack, defaults, picked, topic, work, args.offline)
    print(f"[build] {len(segments)} segments, {total/60:.1f} min", file=sys.stderr)

    video = encode(segments, out_dir, work, defaults["fps"])
    duration = tts.duration_of(video)
    minutes = max(1, round(duration / 60))

    title = pack["title"].format(count=count, minutes=minutes, topic=topic)
    thumb = cards.render_thumbnail(
        out_dir / "thumbnail.png",
        headline=topic if topic else pack["name"],
        sub=f"표현 {count}개 · {minutes}분",
    )

    metadata = {
        "title": title,
        "description": build_description(pack, chapters, count, topic),
        "tags": ["영어공부", "영어회화", "매일영어한마디", "영어듣기", "영어표현",
                 "english listening", "learn english", "shadowing"],
        "categoryId": "27",
        "privacyStatus": "public",
        "duration_seconds": round(duration, 2),
        "phrase_ids": [p["id"] for p in picked],
        "file": str(video.relative_to(ROOT)),
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # An --offline run is a pipeline test, not a publication: recording its
    # phrases would burn them for the next real build.
    if args.offline:
        print("[build] offline run — used.json left unchanged", file=sys.stderr)
    else:
        state.setdefault("packs", {}).setdefault(args.pack, {})
        for p in picked:
            state["packs"][args.pack][p["id"]] = date_str
        if topic:
            state["topic_cursor"] = state.get("topic_cursor", 0) + 1
        save_used(state)

    print(f"[build] {video} ({minutes} min)", file=sys.stderr)
    print(f"[build] thumbnail: {thumb}", file=sys.stderr)
    print(out_dir)  # sole stdout line — the workflow reads this
    return 0


if __name__ == "__main__":
    sys.exit(main())
