"""토크노믹스 대본을 만든다.

    # 발행 스케줄 해부 (외부 데이터 없음, 완전 무료)
    python -m src.run_tokenomics --mode schedule --asset '비트코인' --block-only

    # 실측 희석률 (코인게코, 키 불필요)
    python -m src.run_tokenomics --mode dilution --coin bitcoin --asset '비트코인' --block-only
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from src import tokenomics
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
        prog="src.run_tokenomics", description="토크노믹스 해부"
    )
    parser.add_argument(
        "--mode",
        default="schedule",
        choices=["schedule", "dilution"],
        help="schedule: 반감기 발행 스케줄 / dilution: 실측 유통량 증가율",
    )
    parser.add_argument("--asset", required=True, help="표기용 이름. 예: 비트코인")
    parser.add_argument("--coin", help="dilution: 코인게코 ID. 예: bitcoin, ethereum")
    parser.add_argument(
        "--epochs", type=int, default=8, help="schedule: 표에 넣을 반감기 구간 수"
    )
    parser.add_argument(
        "--days", default="max", help="dilution: 받아올 기간. 기본은 전체."
    )
    parser.add_argument(
        "--periods",
        type=int,
        default=365,
        help="dilution: 증가율을 재는 간격(일). 무료 티어는 받을 수 있는 기간이 "
        "짧을 수 있다. 기록이 모자라면 90 등으로 줄일 것.",
    )
    parser.add_argument("--outdir", default=str(OUT_DIR))
    parser.add_argument(
        "--block-only", action="store_true", help="데이터 블록만 만들고 API 를 호출하지 않는다."
    )
    args = parser.parse_args(argv)
    if args.mode == "dilution" and not args.coin:
        parser.error("--mode dilution 에는 --coin 이 필요하다. 예: --coin bitcoin")
    if args.epochs < 1:
        parser.error("--epochs 는 1 이상이어야 한다.")
    return args


def main(argv=None):
    sys.stdout.reconfigure(line_buffering=True)
    args = parse_args(argv)
    asof = datetime.now().strftime("%Y-%m-%d")

    try:
        if args.mode == "schedule":
            block, rows = tokenomics.build_schedule_block(args.asset, asof, args.epochs)
            print(f"반감기 구간 {len(rows)}개")
            print(f"수렴 총 발행량: {tokenomics.terminal_supply():,.2f}")
            name = f"schedule{args.epochs}"
        else:
            # 다 만들고 나서 키가 없다고 하면 시간만 버린다. 먼저 본다.
            key_problem = tokenomics.check_coingecko_key()
            if key_problem:
                print(f"실패: {key_problem}")
                return 2
            price, cap = tokenomics.fetch_market_chart(args.coin, args.days)
            block, samples = tokenomics.build_dilution_block(
                args.coin, args.asset, price, cap, asof, args.periods
            )
            print(f"관측 구간 {len(samples)}개")
            if samples:
                print(f"최근 전년 대비 유통량 증가율: {samples[-1]['growth']:.2f}%")
            name = f"dilution{args.periods}"
    except tokenomics.TokenomicsError as error:
        print(f"실패: {error}")
        return 3

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"{_slug(args.coin or args.asset)}_{name}_{datetime.now():%Y%m%d-%H%M%S}"
    block_path = outdir / f"{stem}_block.txt"
    block_path.write_text(block, encoding="utf-8")
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
