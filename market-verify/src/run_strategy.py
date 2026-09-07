"""전략 메커니즘 검증 대본을 만든다.

    python -m src.run_strategy --ticker ^GSPC --contrib-months 12 --hold-months 36 \
        --start 1990-01-01 --label 'S&P 500' --block-only

조건 검증(run.py)과 검증기·작성기·영상 파이프라인을 그대로 공유한다.
다른 것은 블록의 내용뿐이다.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from src import market_events as me
from src import strategies
from src.run import KEY_ENV, _slug, add_operator_guide, check_api_key
from src.writer import (
    APICallError,
    ScriptGenerationError,
    format_usage,
    write_script,
)

OUT_DIR = Path(__file__).resolve().parent.parent / "out"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="src.run_strategy", description="분할 매수 대 일시 매수 검증"
    )
    parser.add_argument("--ticker", required=True, help="예: ^GSPC, BTC-USD")
    parser.add_argument("--start", required=True, help="조회 시작일 YYYY-MM-DD")
    parser.add_argument("--end", help="조회 종료일 YYYY-MM-DD")
    parser.add_argument("--label", help="대상 표기용 이름. 예: S&P 500")
    parser.add_argument(
        "--contrib-months", type=int, default=12, help="분할 매수 납입 개월 수"
    )
    parser.add_argument(
        "--hold-months", type=int, default=36, help="시작부터 청산까지 보유 개월 수"
    )
    parser.add_argument(
        "--gap",
        type=int,
        default=strategies.DEFAULT_START_GAP,
        help="시작 시점 간 최소 거래일 간격. 좁히면 같은 국면이 표본으로 부풀어 오른다.",
    )
    parser.add_argument("--outdir", default=str(OUT_DIR))
    parser.add_argument(
        "--block-only", action="store_true", help="데이터 블록만 만들고 API를 호출하지 않는다."
    )
    args = parser.parse_args(argv)
    if args.hold_months < args.contrib_months:
        parser.error("--hold-months 는 --contrib-months 이상이어야 한다.")
    return args


def main(argv=None):
    sys.stdout.reconfigure(line_buffering=True)
    args = parse_args(argv)

    close = me.fetch_close(args.ticker, args.start, args.end)
    block, rows, result = strategies.build_block(
        close,
        ticker=args.ticker,
        contrib_months=args.contrib_months,
        hold_months=args.hold_months,
        asof=datetime.now().strftime("%Y-%m-%d"),
        label=args.label,
        gap=args.gap,
    )

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = (
        f"{_slug(args.ticker)}_dca{args.contrib_months}-hold{args.hold_months}"
        f"_{datetime.now():%Y%m%d-%H%M%S}"
    )
    block_path = outdir / f"{stem}_block.txt"
    block_path.write_text(block, encoding="utf-8")

    print(f"시작 시점 {len(rows)}개")
    if result["dca_win_ratio"] is not None:
        print(
            f"분할 매수가 앞선 비율: {result['dca_win_ratio']:.2f}% "
            f"({result['dca_wins']}/{result['count']})"
        )
    print(f"데이터 블록 저장: {block_path}")

    if args.block_only:
        print("--block-only 이므로 대본은 만들지 않았다.")
        return 0

    key_problem = check_api_key()
    if key_problem:
        print(f"실패: {key_problem}")
        print("데이터 블록은 저장했으니 키만 고치고 다시 실행하면 된다.")
        return 2

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

    try:
        script = write_script(block, on_attempt=report)
    except ScriptGenerationError as error:
        print(f"실패: {error.attempts}회 모두 검증을 통과하지 못했다. 대본을 저장하지 않는다.")
        print(f"최종 위반 {len(error.violations)}건")
        print(format_usage(error.usages))
        return 1
    except APICallError as error:
        print("실패: API 를 호출하지 못했다. 대본을 저장하지 않는다.")
        print(error)
        return 3

    script_path = outdir / f"{stem}_script.md"
    script_path.write_text(add_operator_guide(script), encoding="utf-8")
    print(f"대본 저장: {script_path}")
    print("최종 위반 0건")
    print(format_usage(usages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
