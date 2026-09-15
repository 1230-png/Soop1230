"""매일 새 소재로 롱폼 + 숏폼을 함께 만드는 오케스트레이터.

이 스크립트는 대본·영상 "생성"까지만 자동으로 한다. 업로드는 하지 않는다 —
`src.produce.build()`만 부르고, `--upload`가 있어야 타는 업로드 경로는 아예
호출하지 않는다. 실제 채널에 올리는 건 사람이 결과물을 보고 직접 한다
(`python -m src.produce --script ... --upload`).

    python -m src.daily_pipeline                 # 다음 토픽으로 롱폼+숏폼까지
    python -m src.daily_pipeline --block-only     # 데이터 블록까지만 (API 비용 없음)
    python -m src.daily_pipeline --silent         # 무음 음성으로 영상 조립까지 검증
    python -m src.daily_pipeline --topic-key btc-dilution   # 특정 토픽 지정
"""

import argparse
import sys
from pathlib import Path

from src import (
    news_topics, produce, run, run_macro, run_strategy, run_tokenomics, shorts, topics,
    voice, writer,
)

OUT_DIR = Path(__file__).resolve().parent.parent / "out"

TOOL_MAIN = {
    "run": run.main,
    "run_strategy": run_strategy.main,
    "run_macro": run_macro.main,
    "run_tokenomics": run_tokenomics.main,
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="src.daily_pipeline", description="매일 새 소재로 롱폼+숏폼 생성(업로드 제외)"
    )
    parser.add_argument("--topic-key", help="풀에서 특정 토픽을 지정. 기본은 자동 순환.")
    parser.add_argument("--outdir", default=str(OUT_DIR))
    parser.add_argument("--voice", default=voice.DEFAULT_VOICE)
    parser.add_argument(
        "--silent", action="store_true",
        help="음성 없이 길이만 맞춘 무음으로 만든다. 조립 확인용, 네트워크 안 탐.",
    )
    parser.add_argument(
        "--block-only", action="store_true",
        help="데이터 블록만 만들고 대본·영상은 만들지 않는다(API 비용 없음).",
    )
    parser.add_argument(
        "--shorts-count", type=int, default=None,
        help="만들 숏폼 컷 개수. 기본은 대본에 있는 만큼 전부.",
    )
    parser.add_argument(
        "--log-path", default=str(topics.LOG_PATH), help="토픽 사용 기록 CSV 경로"
    )
    parser.add_argument(
        "--repeat", type=int, default=1,
        help="한 번 실행에 만들 편수. 편마다 다음 토픽으로 넘어간다.",
    )
    parser.add_argument(
        "--source", default="news", choices=["news", "pool"],
        help="news: 어제 크게 움직인 자산에서 소재를 고른다(움직임이 없으면 pool). "
             "pool: 순환 풀에서만 고른다.",
    )
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat 는 1 이상이어야 한다.")
    if args.repeat > 1 and args.topic_key:
        # 같은 토픽을 여러 번 만들어 봐야 같은 영상이 나온다.
        parser.error("--topic-key 는 한 편만 만들 때 쓴다. --repeat 와 함께 쓸 수 없다.")
    return args


def check_outdir(outdir):
    """만들기 전에 저장 폴더를 확인한다. 문제가 없으면 None.

    무인으로 도는 자리다. 드라이브가 빠져 있거나 경로가 틀리면 스택트레이스만
    남아서, 새벽에 실패했을 때 무엇을 고쳐야 하는지 알 수 없다.
    """
    path = Path(outdir)
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError as error:
        return (
            f"저장 폴더를 쓸 수 없다: {path}\n"
            f"  {type(error).__name__}: {error}\n"
            "  드라이브가 연결돼 있는지, 경로와 쓰기 권한이 맞는지 확인할 것."
        )
    return None


def _latest_script(outdir):
    """방금 생성된 대본 파일. run_*.py 는 stem 을 내부에서만 계산하므로
    돌려받는 대신 outdir 에서 가장 최근 파일을 찾는다."""
    found = sorted(Path(outdir).glob("*_script.md"), key=lambda p: p.stat().st_mtime)
    return found[-1] if found else None


def pick_topic(args):
    """오늘 다룰 소재. 어제 움직임 → 없으면 순환 풀."""
    if args.topic_key:
        return topics.topic_by_key(args.topic_key)
    if args.source == "news":
        found = news_topics.topic_from_yesterday(used=topics.used_keys(args.log_path))
        if found:
            return found
        print("어제 눈에 띄는 움직임이 없다. 순환 풀에서 고른다.")
    return topics.next_topic(args.log_path)


def run_once(args):
    """토픽 하나로 롱폼 + 숏폼을 만든다. 종료코드를 돌려준다."""
    topic = pick_topic(args)
    print(f"토픽: {topic.label}  ({topic.tool} · {topic.key})")

    tool_argv = list(topic.argv) + ["--outdir", args.outdir]
    if args.block_only:
        tool_argv.append("--block-only")

    retcode = TOOL_MAIN[topic.tool](tool_argv)
    if retcode != 0:
        print(f"실패: {topic.tool} 이(가) 종료코드 {retcode}로 끝났다. 여기서 멈춘다.")
        return retcode

    if args.block_only:
        print("--block-only 이므로 영상은 만들지 않았다.")
        return 0

    script_path = _latest_script(args.outdir)
    if script_path is None:
        print("실패: 대본 파일(_script.md)을 찾지 못했다.")
        return 3
    script_text = script_path.read_text(encoding="utf-8")
    stem = script_path.stem.replace("_script", "")

    speak = voice.silent_speak if args.silent else voice.edge_tts_speak
    video_path, _thumb_path = produce.build(script_text, args.outdir, stem, speak, args.voice)

    cuts_total = len(shorts.parse_cuts(script_text))
    if cuts_total == 0 and shorts.has_section(script_text):
        # 섹션은 있는데 한 컷도 못 읽었다. 모델이 형식을 바꾼 것이다.
        # 조용히 0개로 넘어가면 숏폼이 안 나오는 줄도 모른다.
        print("  ! 숏폼 컷 섹션을 읽지 못했다. 대본의 표기 형식이 바뀐 것 같다 — 대본을 확인할 것.")
    limit = cuts_total if args.shorts_count is None else min(args.shorts_count, cuts_total)
    short_paths = []
    for index in range(limit):
        try:
            short_paths.append(
                shorts.build(script_text, args.outdir, stem, speak, args.voice, index)
            )
        except shorts.CutNotFoundError as error:
            print(f"  ! 숏폼 컷 {index + 1}번 건너뜀: {error}")

    if limit and not short_paths:
        # 컷은 읽었는데 한 편도 못 만들었다. 인용문이 본문과 어긋난 것이다.
        # 위 건너뜀 줄이 로그에 묻히기 쉬워 한 번 더 못을 박는다.
        print("  ! 숏폼 컷을 읽었는데 한 편도 만들지 못했다. 인용문이 본문과 다르다 — 대본을 확인할 것.")

    topics.record_topic(topic, args.log_path)
    print(f"완료 — 롱폼 1개, 숏폼 {len(short_paths)}개.")
    print("업로드는 하지 않았다. 결과를 확인한 뒤 사람이 src.produce --upload 로 직접 올릴 것.")
    print(f"  롱폼: {video_path}")
    for path in short_paths:
        print(f"  숏폼: {path}")
    return 0


def main(argv=None):
    args = parse_args(argv)

    problem = check_outdir(args.outdir)
    if problem:
        print(f"실패: {problem}")
        return 2

    # 어느 지갑을 쓰는지는 로그에 남겨야 한다. 무인으로 돌 때 헷갈린다.
    print("대본 작성: " + ("Claude Code 구독(claude -p)" if writer.uses_cli() else "API 키"))

    for index in range(1, args.repeat + 1):
        if args.repeat > 1:
            print(f"\n=== {index}/{args.repeat}편 ===")
        code = run_once(args)
        if code != 0:
            # 무인 실행이라 여기서 멈춘다. 같은 원인으로 남은 편까지 토큰만 태울 수 있다.
            print(f"{index}편째에서 멈춘다. 만든 편수: {index - 1}")
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
