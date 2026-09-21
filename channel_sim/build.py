"""정렬 시각화 한 편을 만든다.

    python3 channel_sim/build.py --episode E01
    python3 channel_sim/build.py --episode E01 --preview   # 짧게 한 편 (확인용)

앞선 두 시도와 무엇이 다른가:

- **대본이 없다.** 말로 설명하지 않는다. 화면에서 실제로 계산이 돌아가고,
  소리는 그 계산에서 파생된다. 음성 합성도, 배경음악도 쓰지 않는다.
- **매 편 실제로 다른 계산이 돈다.** 유튜브가 거르는 것은 "기계가 만들었다"가
  아니라 "틀을 반복 재생산했다"이다. 여기서는 알고리즘과 입력이 바뀌면
  화면에 나오는 것이 통째로 달라진다.
- **길이에 명분이 있다.** 버블 정렬이 384개를 정리하는 데 걸리는 시간이 곧
  그 꼭지의 길이다. 늘린 것이 아니라 원래 그만큼 걸린다.

만드는 순서는 두 번에 나눈다. 프레임을 ffmpeg 로 흘려보내면서 소리는 파일로
따로 적고, 다 만든 뒤에 합친다. 한 번에 하려면 두 입력을 동시에 먹여야 하는데
파이프 하나로는 안 되고, 프레임을 전부 디스크에 두면 20분짜리가 200GB 가 된다.
"""

import argparse
import datetime
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import algos, audio, frames  # noqa: E402

ROOT = Path(__file__).resolve().parent
EPISODES_DIR = ROOT / "episodes"
BUILD_ROOT = ROOT / "build"

FPS = 30

# 꼭지 하나의 길이를 사건 수로 정한다. 초당 이만큼을 소화한다고 보고,
# 너무 짧거나 너무 길지 않게 양쪽을 자른다.
#
# 자르는 이유가 양쪽 다르다. 아래쪽은 **너무 빨리 끝나면 무슨 일이
# 일어났는지 안 보이기 때문**이고(기수 정렬은 768번이면 끝난다), 위쪽은
# **버블 정렬을 원래 속도로 다 보여 주면 혼자 십 분을 먹기 때문**이다.
EVENTS_PER_SECOND = 520
MIN_SECONDS = 24
MAX_SECONDS = 100

# 한 프레임에 표시할 수 있는 "지금 만지는 칸"의 최대 개수.
#
# 버블 정렬은 한 프레임에 서른 번 넘게 비교한다. 그걸 전부 칠하면 이미
# 정렬된 왼쪽 절반이 통째로 흰색이 되어 **무엇이 정렬됐는지가 안 보인다.**
# 최근 것만 남기면 작업 지점이 점처럼 움직여 눈이 따라갈 수 있다.
MAX_MARKS = 14

TITLE_HOLD = 2.2       # 꼭지 제목과 섞인 배열을 보여 주는 시간
SWEEP_SECONDS = 1.3    # 다 끝나고 왼쪽부터 초록으로 훑는 시간
REST_SECONDS = 0.7     # 다음 꼭지로 넘어가기 전 정지


def load_episode(episode_id: str) -> dict:
    matches = sorted(EPISODES_DIR.glob(f"{episode_id}-*.yaml"))
    matches += sorted(EPISODES_DIR.glob(f"{episode_id}.yaml"))
    if not matches:
        raise SystemExit(f"{episode_id} 설정이 없다. {EPISODES_DIR} 를 볼 것.")
    return yaml.safe_load(matches[0].read_text(encoding="utf-8"))


def section_seconds(event_count: int, preview: bool) -> float:
    if preview:
        return 3.0
    return float(np.clip(event_count / EVENTS_PER_SECOND, MIN_SECONDS, MAX_SECONDS))


class Writer:
    """ffmpeg 로 흘려보내는 프레임과, 파일로 적는 소리."""

    def __init__(self, video_path: Path, audio_path: Path) -> None:
        self.proc = subprocess.Popen(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{frames.WIDTH}x{frames.HEIGHT}", "-r", str(FPS), "-i", "-",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
             "-pix_fmt", "yuv420p", str(video_path)],
            stdin=subprocess.PIPE)
        self.tone = audio.ToneWriter(audio_path, FPS)
        self.count = 0

    def push(self, frame: np.ndarray, value: float | None, loud: float = 1.0) -> None:
        self.proc.stdin.write(frame.tobytes())
        self.tone.push(value, loud)
        self.count += 1

    def close(self) -> None:
        self.proc.stdin.close()
        self.proc.wait()
        self.tone.close()


def render_card(writer: Writer, card: np.ndarray, seconds: float) -> None:
    """정지 카드. 소리는 쉰다."""
    for _ in range(int(seconds * FPS)):
        writer.push(card, None)


def render_section(writer: Writer, name: str, subtitle: str, index: str,
                   values: list[int], func, preview: bool) -> dict:
    """알고리즘 한 개를 처음부터 끝까지.

    제너레이터를 **두 번** 돌린다. 한 번은 사건 수를 세려고(그래야 꼭지
    길이를 정할 수 있다), 한 번은 실제로 그리려고. 첫 번째 결과를 그대로
    쓸 수 없는 이유는 사건이 인덱스만 담고 값은 담지 않기 때문이다 —
    화면에 그릴 배열 상태는 제너레이터가 살아 있는 동안에만 볼 수 있다.
    """
    events, _ = algos.collect(func, values)
    seconds = section_seconds(len(events), preview)
    total_frames = max(1, int(seconds * FPS))

    chrome = frames.Chrome(name, subtitle, index)
    colors = frames.value_colors(len(values))

    work = list(values)
    state = np.array(work, dtype=np.int32)

    # 섞인 상태를 먼저 보여 준다. 무엇을 정리하는지 보고 나야 그 뒤가 읽힌다.
    frame = chrome.base.copy()
    frames.draw_bars(frame, state, colors)
    frames.paste(frame, frames.counter_patch(0, 0), frames.COUNTER_BOX)
    frames.draw_progress(frame, 0.0)
    render_card(writer, frame, TITLE_HOLD if not preview else 0.5)

    generator = func(work)
    compares = writes = 0
    consumed = 0
    last_touch = None
    exhausted = False
    counter = frames.counter_patch(0, 0)

    for number in range(total_frames):
        # 프레임마다 몇 개를 소화할지 **누적 목표로** 정한다.
        #
        # 프레임당 개수를 실수로 들고 다니며 빚을 갚는 식으로 짰더니, 마지막
        # 프레임에서 사건이 한 개씩 남았다. 제너레이터는 게을러서 그 한 번의
        # next() 안에 마지막 대입이 들어 있다 — 안 부르면 배열이 정렬되지
        # 않은 채로 끝난다. 삽입 정렬이 실제로 그렇게 실패했다.
        #
        # 누적 목표로 두면 마지막 프레임의 목표가 정확히 전체 사건 수가 되어
        # 반올림 오차가 남지 않는다.
        target = round((number + 1) * len(events) / total_frames)
        touched: list[tuple[int, tuple]] = []
        while consumed < target and not exhausted:
            consumed += 1
            try:
                kind, i, j = next(generator)
            except StopIteration:
                exhausted = True
                break
            if kind == "compare":
                compares += 1
                color = frames.COMPARE
            else:
                writes += 1
                color = frames.WRITE
            touched.append((i, color))
            touched.append((j, color))
            last_touch = j

        # 최근 것만 남긴다. dict 로 바로 모으지 않는 이유는 순서가 필요해서다 —
        # 마지막에 만진 칸이 이겨야 쓰기가 비교에 덮이지 않는다.
        marks = dict(touched[-MAX_MARKS:])

        state = np.array(work, dtype=np.int32)
        frame = chrome.base.copy()
        frames.draw_bars(frame, state, colors, marks)

        # 숫자는 초당 여섯 번만 다시 그린다. 매 프레임 그려도 눈에 띄는
        # 차이가 없는데 PIL 호출만 36,000번이 된다.
        if number % 5 == 0:
            counter = frames.counter_patch(compares, writes)
        frames.paste(frame, counter, frames.COUNTER_BOX)
        frames.draw_progress(frame, (number + 1) / total_frames)

        value = None
        if last_touch is not None and marks:
            value = float(state[last_touch]) / len(values)
        writer.push(frame, value, 0.85)

    # 끝났다는 신호. 왼쪽부터 초록으로 훑으면서 음이 같이 올라간다.
    state = np.array(work, dtype=np.int32)
    sweep_frames = max(1, int((SWEEP_SECONDS if not preview else 0.3) * FPS))
    counter = frames.counter_patch(compares, writes)
    for number in range(sweep_frames):
        reached = int(len(values) * (number + 1) / sweep_frames)
        marks = {k: frames.DONE for k in range(reached)}
        frame = chrome.base.copy()
        frames.draw_bars(frame, state, colors, marks)
        frames.paste(frame, counter, frames.COUNTER_BOX)
        frames.draw_progress(frame, 1.0, frames.DONE)
        writer.push(frame, (number + 1) / sweep_frames, 0.7)

    render_card(writer, frame, REST_SECONDS)

    ok = work == sorted(values)
    print(f"[build] {name:14} {seconds:5.1f}초  비교 {compares:7,}  "
          f"쓰기 {writes:6,}  {'정렬됨' if ok else '** 정렬 실패 **'}",
          file=sys.stderr)
    if not ok:
        raise SystemExit(f"{name} 이 배열을 정렬하지 못했다. 발행하지 않는다.")

    return {"key": name, "seconds": seconds, "compares": compares,
            "writes": writes, "events": len(events)}


def ranking_cards(stats: list[dict]) -> list[np.ndarray]:
    """마지막 순위표. 이 영상이 말하려는 것이 여기 다 들어 있다.

    두 장으로 나눈다 — 비교 순서와 쓰기 순서. 한 장에 겹쳐 두면 두 줄이
    서로 다른 순서라는 것이 안 보이고, **그 어긋남이 요점이다.**
    선택 정렬은 비교로 줄을 세우면 꼴찌권인데 쓰기로 세우면 1등이다.
    """
    out = []
    for label, key, note in (
            ("비교 횟수", "compares", "값을 몇 번 들여다봤나"),
            ("쓰기 횟수", "writes", "메모리에 몇 번 적었나")):
        rows = sorted(stats, key=lambda s: s[key])
        out.append(frames.table_card(
            label, note, [(r["key"], f"{r[key]:,}") for r in rows]))
    return out


# 영상이 이보다 짧으면 렌더가 중간에 끊긴 것이다. 정상 빌드는 12분 언저리다.
MIN_SECONDS_TO_PUBLISH = 420


def build_description(episode: dict, stats: list[dict], size: int) -> str:
    """설명문.

    검색 결과와 추천 카드에는 **앞 두 줄만** 보인다. 그 두 줄이 제목을 다시
    말하면 낭비라, 이 영상에서 실제로 무엇을 보게 되는지를 먼저 적는다.

    숫자를 설명문에 그대로 적는 이유는 검색 때문이다. "버블 정렬 비교 횟수"
    같은 질문으로 들어오는 사람이 실제로 있고, 그 숫자가 본문에 있어야 걸린다.
    """
    by_compare = sorted(stats, key=lambda s: s["compares"])
    lines = [
        f"섞인 숫자 {size}개를 정렬 알고리즘 {len(stats)}종이 각자 정리합니다.",
        "소리는 그때 만지고 있는 값의 높이입니다 — 정리될수록 음이 정리됩니다.",
        "",
        "누가 제일 빠른지보다, 무엇을 아끼는지가 서로 다릅니다.",
        f"비교가 가장 적은 것은 {by_compare[0]['key']}"
        f"({by_compare[0]['compares']:,}회), 가장 많은 것은 "
        f"{by_compare[-1]['key']}({by_compare[-1]['compares']:,}회)입니다.",
        "선택 정렬은 비교로 줄을 세우면 꼴찌권인데 쓰기로 세우면 1등입니다.",
        "",
        "이 영상에 나오는 순서",
    ]
    lines += [f"{n:2}. {s['key']}" for n, s in enumerate(stats, 1)]
    lines += [
        "",
        "화면과 소리 모두 코드가 계산해서 만듭니다. 음성도 배경음악도 없습니다.",
        "",
        " ".join(f"#{tag}" for tag in episode.get("tags", [])[:8]),
    ]
    return "\n".join(lines)


def verify_publishable(meta: dict) -> None:
    """발행해도 되는 상태인가. 인코딩이 끝난 뒤, 그리고 올리기 직전에 본다.

    빌드와 업로드는 다른 실행이다. 그 사이에 metadata.json 을 손으로 고쳤을
    수도, --dir 이 예전 폴더를 가리킬 수도 있다. 검사는 공짜고, 한 번 나간
    영상은 되돌리기 번거롭다.
    """
    problems = []

    if meta.get("preview"):
        problems.append("--preview 로 만든 것이다. 꼭지마다 3초씩뿐이라 "
                        "발행용이 아니다")

    if meta.get("duration_seconds", 0) < MIN_SECONDS_TO_PUBLISH:
        problems.append(
            f"{meta.get('duration_seconds', 0):.0f}초뿐이다. 렌더가 중간에 "
            "끊겼을 때 이렇게 된다")

    if len(meta.get("algorithms", [])) != len(algos.ALGORITHMS):
        problems.append(
            f"알고리즘이 {len(meta.get('algorithms', []))}개만 들어 있다. "
            f"{len(algos.ALGORITHMS)}개여야 한다")

    for field in ("title", "description"):
        value = meta.get(field) or ""
        if not value.strip():
            problems.append(f"{field} 가 비어 있다")
        elif "{" in value or "None" in value or "nan" in value:
            problems.append(f"{field} 에 안 채워진 서식 자리가 남아 있다")

    if problems:
        raise SystemExit("발행하지 않는다:\n  - " + "\n  - ".join(problems))


def main() -> int:
    parser = argparse.ArgumentParser(description="정렬 시각화 한 편을 만든다")
    parser.add_argument("--episode", default="E01")
    parser.add_argument("--preview", action="store_true",
                        help="꼭지마다 3초씩만 — 화면과 소리 확인용")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    episode = load_episode(args.episode)
    size = int(episode.get("size", 384))
    seed = int(episode.get("seed", 1))

    rng = random.Random(seed)
    values = rng.sample(range(1, size + 1), size)

    today = datetime.date.today().isoformat()
    out_dir = args.out or BUILD_ROOT / f"{today}-{episode['id']}"
    out_dir.mkdir(parents=True, exist_ok=True)

    silent = out_dir / "silent.mp4"
    pcm = out_dir / "audio.raw"
    writer = Writer(silent, pcm)

    render_card(writer, frames.text_card([
        (episode["title"], 72, True, frames.FG),
        (episode.get("hook", ""), 36, False, frames.DIM),
        ("", 20, False, frames.DIM),
        (f"같은 {size}개를 알고리즘 {len(algos.ALGORITHMS)}종이 각자 정리합니다",
         34, False, frames.FG),
        ("소리는 지금 만지고 있는 값의 높이입니다", 30, False, frames.DIM),
    ]), 7.0 if not args.preview else 1.0)

    stats = []
    for number, (key, name, subtitle, func) in enumerate(algos.ALGORITHMS, 1):
        stats.append(render_section(
            writer, name, subtitle, f"{number:02d} / {len(algos.ALGORITHMS)}",
            values, func, args.preview))

    for card in ranking_cards(stats):
        render_card(writer, card, 9.0 if not args.preview else 1.0)

    writer.close()

    total = writer.count / FPS
    final = out_dir / "video.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(silent),
         "-f", "s16le", "-ar", str(audio.RATE), "-ac", "1", "-i", str(pcm),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
         "-movflags", "+faststart", str(final)],
        check=True)
    silent.unlink()
    pcm.unlink()

    meta = {
        "episode": episode["id"],
        "title": episode["title"],
        "description": build_description(episode, stats, size),
        "tags": episode.get("tags", []),
        "categoryId": "28",     # 과학 기술
        "size": size,
        "seed": seed,
        "duration_seconds": round(total, 2),
        "algorithms": stats,
        "privacyStatus": "private",
        "preview": args.preview,
    }
    verify_publishable(meta)
    (out_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[build] {final} — {total / 60:.1f}분 ({writer.count} 프레임)",
          file=sys.stderr)
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
