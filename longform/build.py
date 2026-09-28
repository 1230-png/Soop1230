"""Build one long-form pack: pick phrases, synthesize, render cards, encode.

    python3 longform/build.py --pack weekly_100 [--offline] [--limit N]

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
    "shadow_gap": "shadow", "recall_gap": "recall",
}

# 유튜브 설명란은 5,000바이트까지다(한글은 한 글자 3바이트). 넘으면 영상을
# 다 만든 뒤 업로드에서 invalidDescription 으로 죽는다 — 150문장 수면 팩과
# 3시간 팩이 챕터를 문장마다 달다가 실제로 그렇게 죽었다(이슈 #28, #29).
# upload.py 가 제휴 고지와 링크(~300바이트)를 덧붙이므로 여유를 둔다.
DESCRIPTION_BUDGET = 4500


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
                 include: list = None) -> list:
    """Unused-first selection, oldest-used as fallback.

    Recycling is per pack, so a phrase that appeared in a shadowing drill is
    still fresh for the monthly review — the two present it differently
    enough that a viewer would not read it as a repeat.

    `include` is the list of `topic` values a themed pack draws from. A pack
    can never return more phrases than its pool holds, so the pool has to be
    the size of a video: the raw topics run 8-16 phrases, which is why
    packs.yaml groups them before they get here.
    """
    if include:
        wanted = set(include)
        pool = [p for p in phrases if p.get("topic") in wanted]
    else:
        pool = list(phrases)
    if not pool:
        raise SystemExit(f"No phrases match topics {include!r}")

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

    Returns (segments, chapters, total_seconds, kept) where each segment is
    {audio, seconds, card} and `kept` is the phrases that actually made it in
    — a phrase whose TTS failed is dropped, so the title, the chapters and
    used.json all have to count from this rather than from what was asked for.
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

    def card_for(part_no: int, label: str, idx: int, phrase: dict,
                 stage: str) -> Path:
        key = (part_no, phrase["id"], stage)
        if key not in card_cache:
            card_cache[key] = cards.render(
                work / f"card_{part_no}_{idx:03d}_{stage}.png",
                phrase=phrase, index=idx, total=count, stage=stage, topic=label,
            )
        return card_cache[key]

    # A pack is one recipe run over the phrases, or several `parts` run one
    # after another. Only the first part decides which phrases survive a TTS
    # failure; a later part dropping one just skips it there.
    parts = pack.get("parts") or [{"recipe": pack["recipe"]}]
    kept = picked
    for part_no, part in enumerate(parts):
        label = part.get("label", "") or topic
        per_phrase_chapters = part.get("chapters", "phrases") == "phrases"
        if not per_phrase_chapters:
            chapters.append((total, label))
        survivors = []

        for idx, phrase in enumerate(kept, start=1):
            # Build each phrase into the segment list, but be ready to take it
            # back out. A 150-phrase sleep pack makes ~450 edge-tts calls, so
            # one of them exhausting its retries is not a remote possibility —
            # and losing a 35-minute pack over a single sentence is a worse
            # outcome than shipping it one sentence short. Rolling back to the
            # mark keeps a half-built phrase from appearing with steps missing.
            mark, mark_total = len(segments), total
            last_en_seconds = 0.0

            def card(stage):
                return card_for(part_no, label, idx, phrase, stage)

            def silence(seconds):
                return tts.make_silence(
                    seconds, work / f"gap_{part_no}_{idx:03d}_{len(segments)}.mp3")

            try:
                for step in part["recipe"]:
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
                        add(audio, card(STAGE[step]))

                    elif step in ("shadow_gap", "recall_gap"):
                        # The whole point: long enough to actually say it back.
                        # A gap the same length as the audio is not — the
                        # learner is still drawing breath — hence the multiplier.
                        # recall_gap comes *before* the English is heard, so it
                        # measures the line it is about to play (cached, so
                        # the en_normal that follows costs nothing extra).
                        if step == "recall_gap":
                            last_en_seconds = tts.duration_of(tts.synthesize(
                                phrase["en"], defaults["voice_en"], "+0%",
                                offline=offline))
                        seconds = (last_en_seconds * defaults.get("shadow_mult", 1.0)
                                   + defaults["shadow_pad"])
                        add(silence(seconds), card(STAGE[step]))

                    elif step.startswith("gap_") and step in defaults:
                        # Hold the last card rather than flashing a new one.
                        add(silence(defaults[step]),
                            segments[-1]["card"] if segments else intro_card)

                    else:
                        raise SystemExit(f"Unknown recipe step: {step}")
            except tts.TTSError as e:
                print(f"[build] dropping {phrase['id']} from part {part_no + 1}: {e}",
                      file=sys.stderr)
                del segments[mark:]
                total = mark_total
                continue

            if per_phrase_chapters:
                chapters.append((mark_total, phrase["en"]))
            survivors.append(phrase)

        if part_no == 0:
            kept = survivors

    # Outro
    outro_card = cards.render_title(
        work / "card_outro.png",
        lines=["오늘도 수고하셨어요"],
        subtitle="구독하시면 다음 영상을 놓치지 않아요",
    )
    chapters.append((total, "마무리"))
    add(tts.synthesize(pack["outro_ko"], defaults["voice_ko"], offline=offline),
        outro_card)

    return segments, chapters, total, kept


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


def build_description(pack: dict, chapters: list, count: int, topic: str,
                      minutes: int) -> str:
    """설명문.

    검색 결과와 추천 카드에는 앞 두 줄만 보인다. 그 두 줄이 제목과 같은 말을
    반복하면 낭비이므로, 무엇을 얻어 가는지와 어떻게 쓰는지를 먼저 적는다.
    타임스탬프는 그 아래로 내린다 — 재생 화면에서만 쓰이지 검색에는 안 쓰인다.
    """
    subject = f"{topic} " if topic else ""
    lines = [
        pack.get("hook", "").format(count=count, minutes=minutes,
                                    topic=topic).strip()
        or f"{subject}영어 회화 표현 {count}개를 {minutes}분에 모아 들었습니다.",
        "한 번에 다 외우지 않아도 됩니다. 반복해서 듣는 것이 가장 빠릅니다.",
        "",
        pack.get("howto", "").strip(),
        "",
        "타임스탬프",
    ]
    tail = [
        "",
        "매일 영어 한마디 — 실생활에서 바로 쓰는 영어 표현을 매일 전해드립니다.",
        "구독: https://www.youtube.com/@200-y3b?sub_confirmation=1",
        "다른 몰아듣기 영상: https://www.youtube.com/@200-y3b/playlists",
        "",
        "[ 업로드 일정 ]",
        "매주 일요일 아침 6시 — 1시간 영어회화 100문장",
        "매일 09시·15시·21시 — 오늘의 표현 한 개 (쇼츠)",
        "",
        " ".join(f"#{t}" for t in pack.get("tags", [])[:5]),
        "#영어공부 #영어회화 #매일영어한마디 #영어듣기 #dailyenglish",
    ]
    pinned = {"인트로", "마무리"} | {p.get("label") for p in pack.get("parts", [])}
    return fit_description(lines, chapters, tail, pinned)


def fit_description(head: list, chapters: list, tail: list,
                    pinned: set = frozenset()) -> str:
    """Thin the timestamps until the whole thing fits DESCRIPTION_BUDGET.

    Every `step`-th phrase chapter survives, plus the pinned ones (0:00 has
    to stay or YouTube shows no chapters at all). `<` and `>` are stripped
    because the API rejects a description containing them.
    """
    step = 1
    while True:
        kept = [c for i, c in enumerate(chapters) if i % step == 0 or c[1] in pinned]
        text = "\n".join(head + [f"{fmt_timestamp(t)} {label}" for t, label in kept]
                         + tail).replace("<", "").replace(">", "")
        if len(text.encode("utf-8")) <= DESCRIPTION_BUDGET or step > len(chapters):
            return text
        step += 1


def pick_theme(pack_id: str, pack: dict, state: dict) -> dict:
    """This week's entry from pack["themes"], with which lap of the rotation
    it is on — the title needs that so a theme's second airing is not a
    word-for-word copy of its first."""
    themes = pack["themes"]
    cursor = state.get("theme_cursor", {}).get(pack_id, 0)
    return dict(themes[cursor % len(themes)], cursor=cursor,
                round=cursor // len(themes) + 1)


def make_title(pack: dict, count: int, minutes: int, topic: str,
               theme: dict = None) -> str:
    """YouTube refuses titles over 100 characters, after the whole build."""
    title = pack["title"].format(
        count=count, minutes=minutes, topic=topic,
        hook=theme["hook"] if theme else "",
        round=f" {theme['round']}탄" if theme and theme["round"] > 1 else "")
    if len(title) > 100:
        raise SystemExit(f"Title is {len(title)} chars (limit 100): {title}")
    return title


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

    topic, include, theme = "", None, None
    if args.pack == "situation_pack":
        topics = config["topics"]
        entry = topics[state.get("topic_cursor", 0) % len(topics)]
        topic, include = entry["name"], entry["include"]
    elif "themes" in pack:
        theme = pick_theme(args.pack, pack, state)
        topic, include = theme["name"], theme["include"]
        # 짧은 문장부터. 채널이 겨누는 검색어가 「왕초보」라 첫 몇 분이 쉬워야
        # 남고, 한 편 안에서도 짧게 시작해 길어지는 순서가 따라 하기 쉽다.
        phrases = sorted(phrases, key=lambda p: len(p["en"].split()))

    count = args.limit or pack["phrase_count"]
    picked = pick_phrases(phrases, args.pack, count, state, include)
    if theme:
        picked.sort(key=lambda p: len(p["en"].split()))
    if len(picked) < count:
        print(f"[build] pool holds {len(picked)} of the {count} phrases asked "
              f"for — the video will be correspondingly shorter", file=sys.stderr)
    count = len(picked)

    date_str = datetime.date.today().isoformat()
    out_dir = BUILD_ROOT / f"{date_str}-{args.pack}"
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)

    print(f"[build] {args.pack}: {count} phrases"
          + (f", topic={topic}" if topic else "")
          + (" (offline)" if args.offline else ""), file=sys.stderr)

    segments, chapters, total, picked = build_segments(
        pack, defaults, picked, topic, work, args.offline)
    if len(picked) < count:
        print(f"[build] {count - len(picked)} phrase(s) dropped on TTS failure",
              file=sys.stderr)
    count = len(picked)
    if not count:
        raise SystemExit("Every phrase failed to synthesize — nothing to publish.")
    print(f"[build] {len(segments)} segments, {total/60:.1f} min", file=sys.stderr)

    video = encode(segments, out_dir, work, defaults["fps"])
    duration = tts.duration_of(video)
    minutes = max(1, round(duration / 60))

    target = pack.get("target_minutes")
    if target and abs(minutes - target) / target > 0.3:
        print(f"::warning::{args.pack} built {minutes}min against a "
              f"target_minutes of {target}. Adjust phrase_count or the "
              f"recipe so the label matches what viewers get.", file=sys.stderr)

    title = make_title(pack, count, minutes, topic, theme)
    thumb = cards.render_thumbnail(
        out_dir / "thumbnail.png",
        headline=pack["name"] if theme else (topic or pack["name"]),
        sub=(f"{topic} · {minutes}분 흘려듣기" if theme
             else f"표현 {count}개 · {minutes}분"),
    )

    metadata = {
        "title": title,
        "description": build_description(pack, chapters, count, topic, minutes),
        # 팩별 태그를 앞에 둔다. 태그는 앞쪽에 가중치가 있고, 공통 태그만으로는
        # 다섯 팩이 전부 같은 검색어를 두고 서로 경쟁한다.
        "tags": pack.get("tags", []) + [
            "영어공부", "영어회화", "매일영어한마디", "영어듣기", "영어표현",
            "english listening", "learn english", "shadowing"],
        "categoryId": "27",
        "privacyStatus": "public",
        # Playlists chain one long-form into the next on autoplay, which is
        # the cheapest watch-time lever available here.
        "playlist": pack.get("playlist", ""),
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
        if theme:
            state.setdefault("theme_cursor", {})
            state["theme_cursor"][args.pack] = theme["cursor"] + 1
        elif topic:
            state["topic_cursor"] = state.get("topic_cursor", 0) + 1
        save_used(state)

    print(f"[build] {video} ({minutes} min)", file=sys.stderr)
    print(f"[build] thumbnail: {thumb}", file=sys.stderr)
    print(out_dir)  # sole stdout line — the workflow reads this
    return 0


if __name__ == "__main__":
    sys.exit(main())
