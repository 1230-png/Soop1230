"""이번 주·이번 달 회차를 묶어 몰아보기 대본을 만든다.

    python -m src.run_recap --window week --outdir out
    python -m src.run_recap --window month --block-only

`run.py` 계열과 같은 자리에 같은 이름 규칙으로 `{stem}_block.txt` 와
`{stem}_script.md` 를 남긴다. 그래야 `daily_pipeline` 의 뒷단(영상·숏폼·업로드)을
그대로 쓴다.

소재는 새로 고르지 않는다. `used_topics.csv` 에 남은 이번 구간의 회차를 되살려
블록만 다시 뽑는다 — 자세한 이유는 `src/recap.py` 머리말에 있다.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from src import recap, run, run_macro, run_strategy, run_tokenomics, topics
from src.run import add_operator_guide
from src.writer import (
    APICallError, MAX_ATTEMPTS, ScriptGenerationError, format_usage,
    load_system_prompt, write_script,
)

OUT_DIR = Path(__file__).resolve().parent.parent / "out"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "recap.md"

TOOL_MAIN = {
    "run": run.main,
    "run_strategy": run_strategy.main,
    "run_macro": run_macro.main,
    "run_tokenomics": run_tokenomics.main,
}

WINDOW_LABEL = {recap.WEEK: "이번 주", recap.MONTH: "이번 달"}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="src.run_recap", description="이번 주·이번 달 회차를 묶은 몰아보기 대본"
    )
    parser.add_argument("--window", default=recap.WEEK, choices=list(recap.WINDOWS))
    parser.add_argument("--outdir", default=str(OUT_DIR))
    parser.add_argument("--log-path", default=str(topics.LOG_PATH))
    parser.add_argument(
        "--block-only", action="store_true",
        help="묶은 데이터 블록까지만 만든다(API 비용 없음).",
    )
    parser.add_argument(
        "--min-episodes", type=int, default=recap.MIN_EPISODES,
        help="이만큼 모이지 않으면 만들지 않는다.",
    )
    return parser.parse_args(argv)


def _block_for(topic, outdir, log=print):
    """토픽 하나의 데이터 블록을 다시 뽑는다. 실패하면 None.

    한 조건이 깨졌다고 묶기를 통째로 포기하지 않는다 — 나머지로도 편이 된다.
    야후에서 데이터를 못 받는 날이 있고, 그 하루 때문에 주간 편이 사라지면
    시청 시간을 쌓으려던 목적 자체가 없어진다.
    """
    before = set(Path(outdir).glob("*_block.txt"))
    argv = list(topic.argv) + ["--outdir", str(outdir), "--block-only"]
    try:
        retcode = TOOL_MAIN[topic.tool](argv)
    except Exception as error:  # noqa: BLE001 - 어떤 실패든 나머지 조건은 살린다
        log(f"  ! {topic.label}: {type(error).__name__} {error}")
        return None
    if retcode != 0:
        log(f"  ! {topic.label}: 종료코드 {retcode}")
        return None
    fresh = sorted(set(Path(outdir).glob("*_block.txt")) - before)
    if not fresh:
        log(f"  ! {topic.label}: 블록 파일을 찾지 못했다.")
        return None
    return fresh[-1].read_text(encoding="utf-8")


def gather(window, outdir, log_path, min_episodes, log=print, now=None):
    """(묶은 블록, 라벨 목록). 묶을 것이 모자라면 (None, [])."""
    rows = recap.episodes_in_window(window, log_path, now)
    label = WINDOW_LABEL[window]
    if len(rows) < min_episodes:
        log(f"{label} 발행한 회차가 {len(rows)}개다. {min_episodes}개는 모여야 묶는다.")
        return None, []

    found = recap.resolve_all(rows, log)
    blocks = []
    for topic in found:
        log(f"  · {topic.label}")
        text = _block_for(topic, outdir, log)
        if text is not None:
            blocks.append((topic.label, text))

    if len(blocks) < min_episodes:
        log(f"블록을 {len(blocks)}개만 세웠다. {min_episodes}개는 있어야 묶는다.")
        return None, []
    return recap.combine_blocks(blocks), [label for label, _ in blocks]


def build(window, outdir, log_path, min_episodes=recap.MIN_EPISODES,
          block_only=False, now=None):
    """몰아보기 대본을 만들고 그 경로를 돌려준다.

    만들 것이 없으면 **None 을 돌려준다.** 종료코드만으로 알리면 부르는 쪽이
    outdir 에 남은 지난 회차 대본을 새로 만든 것으로 착각한다 — 그러면 이미
    발행한 편이 다시 올라간다.

    ScriptGenerationError·APICallError 는 그대로 올려보낸다. 여기서 삼키면
    대본을 못 쓴 것과 묶을 게 없는 것이 구분되지 않는다.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    window_key = recap.window_key(window, now)
    if window_key in topics.used_keys(log_path):
        print(f"{window_key} 은(는) 이미 묶었다. 같은 구간을 두 번 내지 않는다.")
        return None

    print(f"몰아보기: {WINDOW_LABEL[window]} ({window_key})")
    block, labels = gather(window, outdir, log_path, min_episodes, now=now)
    if block is None:
        return None  # 묶을 것이 없는 것은 실패가 아니다.

    stem = f"recap_{window}_{datetime.now():%Y%m%d-%H%M%S}"
    block_path = outdir / f"{stem}_block.txt"
    block_path.write_text(block, encoding="utf-8")
    print(f"조건 {len(labels)}개를 묶었다: {', '.join(labels)}")
    print(f"데이터 블록 저장: {block_path}")

    if block_only:
        print("--block-only 이므로 대본은 만들지 않았다.")
        return None

    usages = []

    def report(attempt, violations, usage):
        usages.append(usage)
        print(
            f"시도 {attempt}: 위반 {len(violations)}건 "
            f"(입력 {usage.input_tokens:,} / 출력 {usage.output_tokens:,} 토큰)"
        )
        if usage.stop_reason == "max_tokens":
            print("  ! 출력이 상한에서 잘렸다. 대본 뒷부분이 통째로 없을 수 있다.")
        for violation in violations:
            print(f"  - {violation}")

    script = write_script(
        block,
        system_prompt=load_system_prompt(PROMPT_PATH),
        max_attempts=MAX_ATTEMPTS,
        on_attempt=report,
    )
    script_path = outdir / f"{stem}_script.md"
    script_path.write_text(add_operator_guide(script), encoding="utf-8")
    print(f"대본 저장: {script_path}")
    print("최종 위반 0건")
    print(format_usage(usages))
    return script_path


def main(argv=None):
    args = parse_args(argv)
    try:
        build(args.window, args.outdir, args.log_path, args.min_episodes,
              args.block_only)
    except ScriptGenerationError as error:
        print(f"실패: {error.attempts}회 모두 검증을 통과하지 못했다. 대본을 저장하지 않는다.")
        print(f"최종 위반 {len(error.violations)}건")
        print(format_usage(error.usages))
        return 1
    except APICallError as error:
        print("실패: API 를 호출하지 못했다. 대본을 저장하지 않는다.")
        print(error)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
