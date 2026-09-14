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

from src import produce, run, run_macro, run_strategy, run_tokenomics, shorts, topics, voice

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
    return parser.parse_args(argv)


def _latest_script(outdir):
    """방금 생성된 대본 파일. run_*.py 는 stem 을 내부에서만 계산하므로
    돌려받는 대신 outdir 에서 가장 최근 파일을 찾는다."""
    found = sorted(Path(outdir).glob("*_script.md"), key=lambda p: p.stat().st_mtime)
    return found[-1] if found else None


def main(argv=None):
    args = parse_args(argv)

    topic = (
        topics.topic_by_key(args.topic_key)
        if args.topic_key
        else topics.next_topic(args.log_path)
    )
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
    limit = cuts_total if args.shorts_count is None else min(args.shorts_count, cuts_total)
    short_paths = []
    for index in range(limit):
        try:
            short_paths.append(
                shorts.build(script_text, args.outdir, stem, speak, args.voice, index)
            )
        except shorts.CutNotFoundError as error:
            print(f"  ! 숏폼 컷 {index + 1}번 건너뜀: {error}")

    topics.record_topic(topic, args.log_path)
    print(f"완료 — 롱폼 1개, 숏폼 {len(short_paths)}개.")
    print("업로드는 하지 않았다. 결과를 확인한 뒤 사람이 src.produce --upload 로 직접 올릴 것.")
    print(f"  롱폼: {video_path}")
    for path in short_paths:
        print(f"  숏폼: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
