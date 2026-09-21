"""저장소에 적어 둔 대본 한 편을 영상으로 만든다.

    python3 channel_cs/build.py --episode E01
    python3 channel_cs/build.py --episode E01 --offline   # 합성 없이 배치만 확인

`channel_jp/build.py` 를 본으로 했고, 세 군데가 다르다.

1. **파이프라인 안에 LLM 호출이 없다.** 대본은 `episodes/*.yaml` 에 사람이
   미리 적어 둔 것을 그대로 읽는다. 앞 채널(Rush22)은 실행마다 모델을 불렀고,
   그 탓에 503 한 번이 발행 실패였고 표현이 미묘하게 겹쳤다. 여기서는 발행
   시점에 외부 지능이 개입하지 않으므로, 돌아가는 동안 품질이 흔들리지 않는다.
2. **문장 은행이 아니라 장면 목록이다.** 일본어 채널은 문장을 골라 쌓지만
   CS 강의는 순서가 곧 논리라, 고를 것이 없다. 한 편은 장면의 배열이고
   장면 하나가 카드 한 장 + 내레이션 한 덩이다.
3. **엔진은 edge 고정.** 이 채널은 결제 수단을 어디에도 걸지 않는다는 전제로
   만든다. elevenlabs 는 글자당 과금이라 애초에 선택지가 아니다.

카드는 정지 화면이라 40분짜리도 인코딩이 몇 분에 끝난다. 움직이는 것은
음성뿐이고, 화면은 장면이 바뀔 때만 바뀐다 — 강의 영상에서는 그것으로 충분하고,
정지 화면이 오히려 코드를 읽기 쉽게 만든다.
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import cards, tts  # noqa: E402

ROOT = Path(__file__).resolve().parent
EPISODES_DIR = ROOT / "episodes"
CURRICULUM = ROOT / "curriculum.yaml"
BUILD_ROOT = ROOT / "build"

# 한국어 남성 음성. 강의 톤이라 또박또박한 쪽을 쓴다.
VOICE = "ko-KR-InJoonNeural"
ENGINE = "edge"
FPS = 2  # 정지 화면이라 더 올릴 이유가 없다. 파일만 커진다.

# 장면과 장면 사이의 숨. 없으면 문장이 붙어 들려 강의가 급해 보인다.
SCENE_PAD = 0.45

# 제목·설명에 이런 글자가 남아 있으면 서식 자리가 안 채워진 것이다.
# 머니로직이 `nan%` 가 박힌 영상을 여드레 동안 낸 적이 있다.
BANNED_IN_TEXT = re.compile(r"\{\w*\}|None|nan|NaN|\[object")

# 실제 길이가 target_minutes 에서 이만큼 넘게 벌어지면 발행하지 않는다.
# 제목과 설명이 시청자에게 거짓말을 하기 때문이다.
LENGTH_TOLERANCE = 0.3

# 이 아래로 나오면 합성이 대부분 실패한 것이다. 롱폼 채널에서 5분짜리는
# 사고지 짧은 영상이 아니다.
MIN_SECONDS = 300


def load_curriculum() -> dict:
    return yaml.safe_load(CURRICULUM.read_text(encoding="utf-8"))


def load_episode(episode_id: str) -> dict:
    """`E01` 로 대본 파일을 찾는다. 파일명 뒤에 뭐가 붙든 상관없다."""
    matches = sorted(EPISODES_DIR.glob(f"{episode_id}-*.yaml"))
    matches += sorted(EPISODES_DIR.glob(f"{episode_id}.yaml"))
    if not matches:
        raise SystemExit(
            f"{episode_id} 대본이 없다. {EPISODES_DIR} 에 "
            f"{episode_id}-제목.yaml 을 둘 것.")
    return yaml.safe_load(matches[0].read_text(encoding="utf-8"))


def verify_script(episode: dict) -> None:
    """합성을 시작하기 전에 대본이 온전한지 본다.

    여기를 지나면 edge-tts 호출이 장면 수만큼 시작된다. 값이 드는 단계는
    아니지만 몇 분이 걸리고, 중간에 빈 내레이션을 만나 터지면 그때까지 만든
    것을 버리게 된다. 검사는 공짜다.
    """
    problems = []
    scenes = episode.get("scenes") or []
    if not scenes:
        problems.append("장면이 하나도 없다")

    for index, scene in enumerate(scenes, 1):
        card = scene.get("card") or {}
        kind = card.get("kind")
        if kind not in RENDERERS:
            problems.append(f"{index}번 장면: 모르는 카드 종류 {kind!r}")
        if not (scene.get("say") or "").strip():
            problems.append(f"{index}번 장면: 내레이션이 비어 있다")
        if kind == "code" and not (card.get("code") or "").strip():
            problems.append(f"{index}번 장면: code 카드인데 코드가 없다")
        # 코드 카드는 ASCII 만 받는다. PIL 은 글자마다 대체 글꼴을 찾아 주지
        # 않아서, 고정폭 글꼴에 없는 한글은 두부(□)로 그려진다. 한국어는
        # 카드 아래 caption 줄에 넣는다.
        for field in ("code", "command", "output"):
            value = card.get(field) or ""
            if value and not value.isascii():
                problems.append(
                    f"{index}번 장면: {field} 에 ASCII 가 아닌 글자가 있다. "
                    "고정폭 글꼴에 없으면 □ 로 나온다 — 한국어는 caption 으로.")

    if problems:
        raise SystemExit("대본이 온전하지 않아 합성을 시작하지 않는다:\n  - "
                         + "\n  - ".join(problems))


def verify_publishable(meta: dict, minutes: int, target: int) -> None:
    """발행해도 되는 상태인가. 인코딩이 끝난 뒤 마지막으로 본다.

    실패해도 파일은 남긴다 — 무엇이 잘못됐는지 봐야 고치므로. 다만 0 이 아닌
    코드로 끝나서 워크플로의 업로드 단계가 돌지 않는다.
    """
    problems = []

    for field in ("title", "description"):
        found = BANNED_IN_TEXT.search(meta.get(field) or "")
        if found:
            problems.append(
                f"{field} 에 {found.group(0)!r} 가 들어 있다. 값이 깨졌거나 "
                f"서식 자리가 안 채워졌다:\n    {(meta.get(field) or '')[:120]}")

    if not meta.get("scene_count"):
        problems.append("영상에 들어간 장면이 하나도 없다")

    if meta.get("duration_seconds", 0) < MIN_SECONDS:
        problems.append(
            f"영상이 {meta.get('duration_seconds', 0):.0f}초뿐이다. "
            "합성이 대부분 실패했을 때 이렇게 된다")

    if target and abs(minutes - target) / target > LENGTH_TOLERANCE:
        problems.append(
            f"{minutes}분으로 나왔는데 target_minutes 는 {target}분이다. "
            "제목과 설명이 시청자에게 거짓말을 한다 — 대본 분량을 맞출 것")

    if problems:
        raise SystemExit("발행하지 않는다:\n  - " + "\n  - ".join(problems))


# 카드 종류 → 렌더러. 대본의 `kind` 가 그대로 이 열쇠다.
RENDERERS = {
    "title": "title",
    "talk": "talk",
    "code": "code",
    "terminal": "terminal",
    "diagram": "diagram",
}


def render_card(card: dict, out: Path, episode: dict, season_name: str) -> Path:
    """장면 하나의 화면. 대본의 값을 렌더러 인자로 옮기기만 한다."""
    kind = card["kind"]
    if kind == "title":
        return cards.render_title(
            out, title=episode["title"], hook=episode.get("hook", ""),
            season=season_name, number=episode["id"])
    if kind == "talk":
        return cards.render_talk(
            out, chip=card.get("chip", ""), heading=card.get("heading", ""),
            points=card.get("points", []))
    if kind == "code":
        return cards.render_code(
            out, chip=card.get("chip", ""), lang=card.get("lang", "c"),
            code=card["code"], highlight=card.get("highlight"),
            caption=card.get("caption", ""))
    if kind == "terminal":
        return cards.render_terminal(
            out, chip=card.get("chip", ""), command=card.get("command", ""),
            output=card.get("output", ""), caption=card.get("caption", ""))
    if kind == "diagram":
        # 대본에서는 `shape` 다. 카드에도 `kind` 가 있어 이름이 겹치기 때문에,
        # 대본 쪽 이름을 바꿨다 — 사람이 읽고 쓰는 것은 대본이다.
        return cards.render_diagram(
            out, chip=card.get("chip", ""), kind=card.get("shape", "stack"),
            rows=card.get("rows", []), caption=card.get("caption", ""))
    raise SystemExit(f"모르는 카드 종류: {kind!r}")


def fmt_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def build_segments(episode: dict, season_name: str, work: Path,
                   offline: bool) -> tuple[list, list, float]:
    """장면마다 카드와 음성을 만들고 길이를 잰다."""
    segments, chapters = [], []
    total = 0.0

    for index, scene in enumerate(episode["scenes"], 1):
        card_path = work / f"card-{index:03d}.png"
        render_card(scene["card"], card_path, episode, season_name)

        audio = tts.synthesize(scene["say"].strip(), VOICE,
                               offline=offline, engine=ENGINE)
        seconds = tts.duration_of(audio) + SCENE_PAD

        chapter = (scene.get("chapter") or "").strip()
        if chapter:
            chapters.append((total, chapter))

        segments.append({"card": card_path, "audio": audio, "seconds": seconds})
        total += seconds
        print(f"[build] {index:>3}/{len(episode['scenes'])} "
              f"{seconds:5.1f}초  {scene['say'][:34]}", file=sys.stderr)

    return segments, chapters, total


def encode(segments: list, out_dir: Path, work: Path) -> Path:
    """음성을 잇고, 정지 화면을 잇고, 합친다."""
    # 장면 사이의 숨. 카드는 SCENE_PAD 만큼 더 떠 있으므로, 소리 쪽에도 같은
    # 길이의 무음을 끼워야 화면과 소리가 어긋나지 않는다. 한 장면에서 0.45초씩
    # 밀리면 40분 끝에서는 카드가 한 장 통째로 밀린다.
    pad = tts.make_silence(SCENE_PAD, work / "pad.mp3")
    lines = []
    for segment in segments:
        lines.append(f"file '{segment['audio'].resolve()}'")
        lines.append(f"file '{pad.resolve()}'")
    audio_list = work / "audio.txt"
    audio_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

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
         "-crf", "26", "-r", str(FPS), "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-shortest", "-movflags", "+faststart",
         str(out_path)],
        check=True, capture_output=True)
    return out_path


def build_description(episode: dict, curriculum: dict, chapters: list) -> str:
    """설명문.

    검색 결과와 추천 카드에는 **앞 두 줄만** 보인다. 그 두 줄이 제목을 다시
    말하면 낭비라, 이 영상을 보고 무엇을 알게 되는지를 먼저 적는다.
    타임스탬프는 그 아래다 — 재생 화면에서만 쓰이지 검색에는 안 쓰인다.
    """
    lines = [
        (episode.get("summary") or "").strip(),
        "",
        (episode.get("takeaway") or "").strip(),
        "",
        "타임스탬프",
    ]
    lines += [f"{fmt_timestamp(at)} {label}" for at, label in chapters]

    channel = curriculum["channel"]
    lines += [
        "",
        f"{channel['name']} — 학교에서 배웠지만 실무에서 왜 중요한지 몰랐던 "
        "CS를 다시 봅니다.",
        "",
        "[ 업로드 ] 매주 화·금 저녁 9시",
        "",
        " ".join(f"#{tag}" for tag in episode.get("tags", [])[:6]),
    ]
    return "\n".join(line for line in lines if line is not None)


def season_name(curriculum: dict, season_id: str) -> str:
    for season in curriculum.get("seasons", []):
        if season["id"] == season_id:
            return season["name"]
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="대본 한 편을 영상으로 만든다")
    parser.add_argument("--episode", required=True, help="예: E01")
    parser.add_argument("--offline", action="store_true",
                        help="합성 없이 무음으로 — 배치와 길이만 확인한다")
    parser.add_argument("--out", type=Path, help="빌드 폴더 (기본: build/<날짜>-<편>)")
    args = parser.parse_args()

    curriculum = load_curriculum()
    episode = load_episode(args.episode)

    # 네트워크를 타기 전에 값싼 검사를 전부 끝낸다.
    verify_script(episode)

    today = datetime.date.today().isoformat()
    out_dir = args.out or BUILD_ROOT / f"{today}-{episode['id']}"
    out_dir.mkdir(parents=True, exist_ok=True)

    season = season_name(curriculum, episode.get("season", ""))

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        segments, chapters, total = build_segments(
            episode, season, work, args.offline)
        video = encode(segments, out_dir, work)

    cards.render_thumbnail(out_dir / "thumbnail.png", title=episode["title"],
                           hook=episode.get("hook", ""), number=episode["id"])

    minutes = max(1, round(total / 60))
    meta = {
        "episode": episode["id"],
        "season": episode.get("season", ""),
        "title": episode["title"],
        "description": build_description(episode, curriculum, chapters),
        "tags": episode.get("tags", []),
        "categoryId": "28",     # Science & Technology
        "playlist": f"{episode.get('season', '')} {season}".strip(),
        # private 으로 적어 둔다. 사람이 한 번 보고 공개하라는 뜻이고,
        # 그 기본값을 코드가 조용히 뒤집지 않는다.
        "privacyStatus": "private",
        "duration_seconds": round(total, 2),
        "target_minutes": episode.get("target_minutes"),
        "scene_count": len(segments),
        "chapters": [[round(at, 2), label] for at, label in chapters],
        "offline": args.offline,
    }
    verify_publishable(meta, minutes, episode.get("target_minutes"))

    (out_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[build] {video} — {minutes}분 ({total:.0f}초), "
          f"장면 {len(segments)}개", file=sys.stderr)
    print(out_dir)      # 표준 출력의 유일한 줄. 업로드 단계가 이것을 받는다.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
