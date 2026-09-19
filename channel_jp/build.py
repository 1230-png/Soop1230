"""롱폼 팩 한 편을 만든다: 문장 고르기 → 합성 → 카드 → 인코딩.

    python3 channel_jp/build.py --pack sleep_japanese [--offline] [--limit N]

결과는 `channel_jp/build/<날짜>-<팩>/` 에 video.mp4 · metadata.json ·
thumbnail.png 로 떨어진다.

`longform/build.py`(영어)에서 갈라져 나왔다. 언어 단계 이름 말고 실질적으로
다른 것은 **검사를 두 군데 세운 것**이다.

머니로직은 제목에 `nan%` 가 박힌 영상을 여드레 동안 공개로 올렸다. 원인은
`float('nan') >= 0` 이 False 라 항상 "하락"으로 갈라진 것이었지만, 진짜 문제는
깨진 값이 아무 저항 없이 발행까지 흘러간 것이다. 그래서 여기는 두 번 막는다.

- 합성 **전에** 문장을 검사한다. 깨진 문장이면 edge-tts 를 450번 부르기 전에
  멈춘다. 돈이 드는 단계 앞에 검사를 둔다는 CLAUDE.md 규칙과 같은 자리다.
- 인코딩 **후에** metadata 를 검사한다. 여기를 통과하지 못하면 파일을 남기되
  0 이 아닌 코드로 끝나므로 워크플로의 업로드 단계가 돌지 않는다.
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_bank  # noqa: E402
from lib import cards, tts  # noqa: E402

ROOT = Path(__file__).resolve().parent
PACKS_FILE = ROOT / "packs.yaml"
PHRASES_FILE = ROOT / "data" / "phrases.json"
USED_FILE = ROOT / "data" / "used.json"
BUILD_ROOT = ROOT / "build"

# 소리를 내는 단계와, 각각이 쓰는 음성·속도. 여기 없는 것은 전부 무음이다.
SPOKEN = {
    "ja_normal": ("ja", "voice_ja", None),
    "ja_slow": ("ja", "voice_ja_alt", "rate_slow"),
    "ko": ("ko", "voice_ko", None),
    "example_ja": ("example_ja", "voice_ja", None),
    "example_ko": ("example_ko", "voice_ko", None),
}
# 각 단계에서 카드의 어느 줄에 불을 켤지.
STAGE = {
    "ja_normal": "ja", "ja_slow": "ja", "ko": "ko",
    "example_ja": "example", "example_ko": "example",
    "shadow_gap": "shadow",
}

# 제목·설명에 나오면 안 되는 것. 값이 깨졌을 때 파이썬이 남기는 흔적들이다.
#
# 경계를 `\b` 로 잡으면 안 된다. 파이썬의 `\b` 는 유니코드 기준이고 한글도
# 단어 문자라서, 「문장 None개를 모았습니다」의 `None` 과 `개` 사이에는 경계가
# 생기지 않는다 — 깨진 값이 한국어 문장에 박힌 바로 그 모양인데 그냥 지나간다.
# 그래서 좌우를 **로마자만** 으로 막는다. 「난바(nanba)」 같은 멀쩡한 제목은
# 오른쪽이 로마자라 걸리지 않고, 「None개」는 걸린다.
BANNED_IN_TEXT = re.compile(
    r"(?<![A-Za-z])(?:nan|none|null)(?![A-Za-z])|\{[a-z_]+\}", re.I)

# 완성된 영상이 target_minutes 에서 이만큼 넘게 벗어나면 발행하지 않는다.
LENGTH_TOLERANCE = 0.3


def load_packs() -> dict:
    return yaml.safe_load(PACKS_FILE.read_text(encoding="utf-8"))


def load_phrases() -> list:
    if not PHRASES_FILE.exists():
        raise SystemExit(
            f"{PHRASES_FILE} 이 없다. 먼저 만들 것:\n"
            "  python3 channel_jp/build_bank.py")
    return json.loads(PHRASES_FILE.read_text(encoding="utf-8"))


def load_used() -> dict:
    if USED_FILE.exists():
        return json.loads(USED_FILE.read_text(encoding="utf-8"))
    return {"packs": {}, "topic_cursor": 0}


def save_used(state: dict) -> None:
    USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    USED_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")


def verify_phrases(picked: list) -> None:
    """고른 문장이 온전한지. 합성 한 번 하기 전에 본다.

    `build_bank.py` 가 은행을 만들 때 이미 검사하지만, 그 뒤에 누가
    phrases.json 을 손으로 고쳤을 수 있다. 여기가 마지막이고, 여기를 지나면
    edge-tts 호출이 시작된다 — 수면 팩 한 편이 450번이다.
    """
    problems = []
    for index, phrase in enumerate(picked):
        problems += build_bank.check_entry("phrases.json", index, phrase)
    if problems:
        raise SystemExit(
            "고른 문장이 온전하지 않아 합성을 시작하지 않는다:\n"
            + "\n".join(problems))


def verify_publishable(metadata: dict, minutes: int, target: int) -> None:
    """발행해도 되는 상태인가. 인코딩이 끝난 뒤 마지막으로 본다.

    실패하면 파일은 남긴다 — 무엇이 잘못됐는지 봐야 고치므로. 다만 0 이 아닌
    코드로 끝나서 워크플로의 업로드 단계가 돌지 않는다.
    """
    problems = []

    for field in ("title", "description"):
        found = BANNED_IN_TEXT.search(metadata[field])
        if found:
            problems.append(
                f"{field} 에 {found.group(0)!r} 가 들어 있다. 값이 깨졌거나 "
                f"서식 자리가 안 채워졌다:\n    {metadata[field][:120]}")

    if not metadata["phrase_ids"]:
        problems.append("영상에 들어간 문장이 하나도 없다")

    if metadata["duration_seconds"] < 60:
        problems.append(
            f"영상이 {metadata['duration_seconds']:.0f}초뿐이다. "
            "합성이 대부분 실패했을 때 이렇게 된다")

    if target and abs(minutes - target) / target > LENGTH_TOLERANCE:
        problems.append(
            f"{minutes}분으로 나왔는데 target_minutes 는 {target}분이다. "
            "제목과 설명이 시청자에게 거짓말을 한다 — phrase_count 나 "
            "레시피를 맞출 것")

    if problems:
        raise SystemExit("발행하지 않는다:\n  - " + "\n  - ".join(problems))


def pick_phrases(phrases: list, pack_id: str, count: int, state: dict,
                 include: list = None) -> list:
    """안 쓴 것 먼저, 모자라면 오래된 것부터 다시 쓴다.

    재사용은 팩마다 따로 센다. 쉐도잉에 나온 문장은 수면 팩에서는 여전히
    새 것이다 — 두 팩이 같은 문장을 충분히 다르게 보여 주므로 시청자가
    반복으로 읽지 않는다.
    """
    if include:
        wanted = set(include)
        pool = [p for p in phrases if p.get("topic") in wanted]
    else:
        pool = list(phrases)
    if not pool:
        raise SystemExit(f"주제 {include!r} 에 해당하는 문장이 없다")

    seen = state.get("packs", {}).get(pack_id, {})
    unused = [p for p in pool if p["id"] not in seen]
    picked = unused[:count]

    if len(picked) < count:
        # 오래된 것부터. 그래야 재사용이 고르게 퍼지고 매번 같은 몇 개만
        # 돌려쓰지 않는다.
        rest = sorted((p for p in pool if p["id"] in seen),
                      key=lambda p: seen[p["id"]])
        picked += rest[: count - len(picked)]

    if not picked:
        raise SystemExit(f"{pack_id} 에 넣을 문장을 하나도 고르지 못했다")
    return picked


def fmt_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def build_segments(pack: dict, defaults: dict, picked: list, topic: str,
                   work: Path, offline: bool):
    """인트로 + 문장별 레시피 + 아웃트로를 평평한 구간 목록으로 편다.

    (segments, chapters, total_seconds, kept) 를 돌려준다. 합성이 실패한
    문장은 빠지므로, 제목·챕터·used.json 은 **요청한 수가 아니라 kept** 를
    세야 한다.
    """
    segments, chapters, kept = [], [], []
    total = 0.0
    count = len(picked)

    def add(audio: Path, card: Path):
        nonlocal total
        seconds = tts.duration_of(audio)
        segments.append({"audio": audio, "seconds": seconds, "card": card})
        total += seconds

    intro_card = cards.render_title(
        work / "card_intro.png",
        lines=[pack["name"]],
        subtitle=f"문장 {count}개")
    add(tts.synthesize(pack["intro_ko"], defaults["voice_ko"],
                       offline=offline,
                       engine=defaults.get("engine", "elevenlabs")),
        intro_card)
    chapters.append((0.0, "인트로"))

    card_cache: dict = {}

    def card_for(index: int, phrase: dict, stage: str) -> Path:
        key = (phrase["id"], stage)
        if key not in card_cache:
            card_cache[key] = cards.render(
                work / f"card_{index:03d}_{stage}.png",
                phrase=phrase, index=index, total=count, stage=stage,
                topic=topic)
        return card_cache[key]

    for index, phrase in enumerate(picked, start=1):
        # 문장 하나를 구간 목록에 쌓되 되물릴 준비를 한다. 수면 팩 한 편이
        # edge-tts 를 450번 부르므로 그중 하나가 재시도를 다 쓰는 것은 드문
        # 일이 아니다. 한 문장 때문에 40분짜리를 통째로 잃는 것보다 한 문장
        # 짧게 내보내는 편이 낫고, 표시로 되감으면 반쯤 만들어진 문장이
        # 단계가 빠진 채 나오지 않는다.
        mark, mark_total = len(segments), total
        last_ja_seconds = 0.0

        try:
            for step in pack["recipe"]:
                if step in SPOKEN:
                    kind, voice_key, rate_key = SPOKEN[step]
                    text = {
                        "ja": phrase["ja"],
                        "ko": phrase["ko"],
                        "example_ja": phrase.get("ex_ja", ""),
                        "example_ko": phrase.get("ex_ko", ""),
                    }[kind]
                    if not text:
                        continue    # 예문이 없는 문장. 무음을 넣지 말고 건너뛴다
                    rate = defaults[rate_key] if rate_key else "+0%"
                    audio = tts.synthesize(
                        text, defaults[voice_key], rate, offline=offline,
                        engine=defaults.get("engine", "elevenlabs"))
                    if kind in ("ja", "example_ja"):
                        last_ja_seconds = tts.duration_of(audio)
                    add(audio, card_for(index, phrase, STAGE[step]))

                elif step == "shadow_gap":
                    # 요점은 이것이다: 실제로 따라 말할 수 있을 만큼 길어야
                    # 한다. 음성과 같은 길이로는 안 된다 — 그때 학습자는 아직
                    # 숨을 고르는 중이다. 그래서 배수를 얹는다.
                    seconds = (last_ja_seconds * defaults.get("shadow_mult", 1.0)
                               + defaults["shadow_pad"])
                    audio = tts.make_silence(
                        seconds, work / f"gap_{index:03d}_{len(segments)}.mp3")
                    add(audio, card_for(index, phrase, "shadow"))

                elif step.startswith("gap_") and step in defaults:
                    audio = tts.make_silence(
                        defaults[step],
                        work / f"gap_{index:03d}_{len(segments)}.mp3")
                    # 새 카드를 번쩍이지 말고 직전 카드를 붙들고 있는다.
                    add(audio, segments[-1]["card"] if segments else intro_card)

                else:
                    raise SystemExit(f"모르는 레시피 단계: {step}")
        except tts.TTSError as error:
            print(f"[build] {phrase['id']} 를 뺀다: {error}", file=sys.stderr)
            del segments[mark:]
            total = mark_total
            continue

        chapters.append((mark_total, phrase["ja"]))
        kept.append(phrase)

    outro_card = cards.render_title(
        work / "card_outro.png",
        lines=["오늘도 수고하셨어요"],
        subtitle="구독하시면 다음 영상을 놓치지 않아요")
    chapters.append((total, "마무리"))
    add(tts.synthesize(pack["outro_ko"], defaults["voice_ko"],
                       offline=offline,
                       engine=defaults.get("engine", "elevenlabs")),
        outro_card)

    return segments, chapters, total, kept


def encode(segments: list, out_dir: Path, work: Path, fps: int) -> Path:
    """음성을 잇고, 정지 화면을 잇고, 합친다.

    정지 화면 + 음성 복사라 40분짜리 인코딩이 몇 분에 끝난다.
    """
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
    for segment in segments:
        lines.append(f"file '{segment['card'].resolve()}'")
        lines.append(f"duration {segment['seconds']:.3f}")
    # concat demuxer 는 마지막 항목의 duration 을 버린다. 그래서 마지막
    # 이미지를 duration 없이 한 번 더 적어야 닫는 카드가 잘리지 않는다.
    lines.append(f"file '{segments[-1]['card'].resolve()}'")
    (work / "video.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    out_path = out_dir / "video.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "concat", "-safe", "0", "-i", str(work / "video.txt"),
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
    lines = [
        pack.get("hook", "").format(count=count, minutes=minutes,
                                    topic=topic).strip(),
        "한 번에 다 외우지 않아도 됩니다. 반복해서 듣는 것이 가장 빠릅니다.",
        "",
        pack.get("howto", "").strip(),
        "",
        "타임스탬프",
    ]
    lines += [f"{fmt_timestamp(at)} {label}" for at, label in chapters]
    lines += [
        "",
        "귀트는 일본어 — 한국어로 배우는 일본어 회화를 매주 전해드립니다.",
        "",
        "[ 업로드 일정 ]",
        "화요일 상황별 일본어 · 목요일 쉐도잉 · 금요일 자기 전 일본어",
        "",
        " ".join(f"#{tag}" for tag in pack.get("tags", [])[:5]),
        "#일본어공부 #일본어회화 #일본어듣기 #JLPT #일본어초보",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="롱폼 팩 한 편을 만든다")
    parser.add_argument("--pack", required=True)
    parser.add_argument("--offline", action="store_true",
                        help="TTS 대신 무음 — 네트워크 없이 파이프라인만 검증")
    parser.add_argument("--limit", type=int,
                        help="팩의 문장 수를 덮어쓴다 (빠른 시험용)")
    args = parser.parse_args()

    config = load_packs()
    if args.pack not in config["packs"]:
        raise SystemExit(f"모르는 팩 {args.pack!r}. "
                         f"있는 것: {', '.join(config['packs'])}")
    pack = config["packs"][args.pack]
    defaults = config["defaults"]

    phrases = load_phrases()
    state = load_used()

    topic, include = "", None
    if args.pack == "situation_pack":
        topics = config["topics"]
        entry = topics[state.get("topic_cursor", 0) % len(topics)]
        topic, include = entry["name"], entry["include"]

    count = args.limit or pack["phrase_count"]
    picked = pick_phrases(phrases, args.pack, count, state, include)
    if len(picked) < count:
        print(f"[build] 후보가 {len(picked)}개뿐이다 (요청 {count}개) — "
              f"영상이 그만큼 짧아진다", file=sys.stderr)
    count = len(picked)

    verify_phrases(picked)      # 합성을 시작하기 전에 막는다

    date_str = datetime.date.today().isoformat()
    out_dir = BUILD_ROOT / f"{date_str}-{args.pack}"
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)

    print(f"[build] {args.pack}: 문장 {count}개"
          + (f", 주제={topic}" if topic else "")
          + (" (offline)" if args.offline else ""), file=sys.stderr)

    segments, chapters, total, picked = build_segments(
        pack, defaults, picked, topic, work, args.offline)
    if len(picked) < count:
        print(f"[build] 합성 실패로 {count - len(picked)}개를 뺐다", file=sys.stderr)
    count = len(picked)
    if not count:
        raise SystemExit("모든 문장의 합성이 실패했다 — 낼 것이 없다.")
    print(f"[build] 구간 {len(segments)}개, {total/60:.1f}분", file=sys.stderr)

    video = encode(segments, out_dir, work, defaults["fps"])
    duration = tts.duration_of(video)
    minutes = max(1, round(duration / 60))

    metadata = {
        # 팩 이름과 목표 길이를 남긴다. upload.py 가 올리기 직전에 같은 검사를
        # 다시 하는데, 그때 이 둘이 없으면 길이가 이름표와 맞는지 볼 수 없다.
        "pack": args.pack,
        "target_minutes": pack.get("target_minutes"),
        "title": pack["title"].format(count=count, minutes=minutes, topic=topic),
        "description": build_description(pack, chapters, count, topic, minutes),
        # 팩별 태그를 앞에 둔다. 태그는 앞쪽에 가중치가 있고, 공통 태그만으로는
        # 세 팩이 전부 같은 검색어를 두고 서로 경쟁한다.
        "tags": pack.get("tags", []) + [
            "일본어공부", "일본어회화", "일본어듣기", "일본어초보", "JLPT",
            "learn japanese", "japanese listening"],
        "categoryId": "27",
        # 사람이 한 번 보고 올린다. 무인 공개 발행은 채널이 자리를 잡은 뒤에
        # 다시 이야기한다 — 머니로직이 무인으로 여드레 동안 깨진 영상을 냈다.
        "privacyStatus": "private",
        # 재생목록이 한 편에서 다음 편으로 자동 재생을 잇는다. 여기서 쓸 수
        # 있는 시청 시간 지렛대 중 가장 싸다.
        "playlist": pack.get("playlist", ""),
        "duration_seconds": round(duration, 2),
        "phrase_ids": [p["id"] for p in picked],
        "file": str(video.relative_to(ROOT)),
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    cards.render_thumbnail(
        out_dir / "thumbnail.png",
        headline=topic if topic else pack["name"],
        sub=f"문장 {count}개 · {minutes}분")

    # --offline 은 파이프라인 시험이지 발행이 아니다. 여기서 문장을 기록하면
    # 다음 진짜 빌드에서 그 문장들이 이미 쓴 것으로 빠진다.
    if args.offline:
        print("[build] offline 실행 — used.json 을 건드리지 않았다", file=sys.stderr)
    else:
        state.setdefault("packs", {}).setdefault(args.pack, {})
        for phrase in picked:
            state["packs"][args.pack][phrase["id"]] = date_str
        if topic:
            state["topic_cursor"] = state.get("topic_cursor", 0) + 1
        save_used(state)

    print(f"[build] {video} ({minutes}분)", file=sys.stderr)

    # 마지막 관문. 여기서 멈추면 파일은 남지만 0 이 아닌 코드로 끝나서
    # 워크플로의 업로드 단계가 돌지 않는다.
    #
    # --limit 을 준 실행에서는 길이를 재지 않는다. 그 깃발은 문장 수를 일부러
    # 줄여 파이프라인만 빠르게 보려는 것이라, 짧게 나오는 것이 정상이다.
    # 여기서 걸면 시험 실행이 매번 실패로 끝나고, 그러면 사람이 검사 자체를
    # 꺼 버린다 — 정작 진짜 빌드에서 필요한 검사를.
    verify_publishable(metadata, minutes,
                       None if args.limit else pack.get("target_minutes"))

    print(out_dir)      # 표준 출력의 유일한 줄 — 워크플로가 이것을 읽는다
    return 0


if __name__ == "__main__":
    sys.exit(main())
