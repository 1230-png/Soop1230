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
        prog="src.run_strategy", description="수학적 투자 전략의 메커니즘 검증"
    )
    parser.add_argument(
        "--strategy",
        default="dca",
        choices=["dca", "rebalance"],
        help="dca: 분할 매수 대 일시 매수 / rebalance: 리밸런싱 주기 비교",
    )
    parser.add_argument("--ticker", required=True, help="예: ^GSPC, BTC-USD")
    parser.add_argument("--ticker-b", help="rebalance: 두 번째 자산. 예: AGG")
    parser.add_argument("--label-b", help="rebalance: 두 번째 자산 표기용 이름")
    parser.add_argument(
        "--weight", type=float, default=0.6, help="rebalance: 첫 번째 자산 비중 (0~1)"
    )
    parser.add_argument(
        "--intervals",
        default="0,3,12",
        help="rebalance: 비교할 리밸런싱 주기(개월), 쉼표로 구분. 0 은 리밸런싱 없음.",
    )
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
    if args.strategy == "dca":
        if args.hold_months < args.contrib_months:
            parser.error("--hold-months 는 --contrib-months 이상이어야 한다.")
        return args

    if not args.ticker_b:
        parser.error("--strategy rebalance 에는 --ticker-b 가 필요하다.")
    if not 0.0 < args.weight < 1.0:
        parser.error("--weight 는 0 과 1 사이여야 한다.")
    try:
        args.interval_months = [int(v) for v in args.intervals.split(",") if v.strip()]
    except ValueError:
        parser.error("--intervals 는 쉼표로 구분한 정수여야 한다. 예: 0,3,12")
    if not args.interval_months:
        parser.error("--intervals 가 비었다.")
    for months in args.interval_months:
        if months < 0:
            parser.error("리밸런싱 주기는 0 이상이어야 한다.")
        if months > args.hold_months:
            parser.error(f"주기({months}개월)가 --hold-months 보다 길다.")
    return args


def main(argv=None):
    sys.stdout.reconfigure(line_buffering=True)
    args = parse_args(argv)

    asof = datetime.now().strftime("%Y-%m-%d")
    close = me.fetch_close(args.ticker, args.start, args.end)

    if args.strategy == "dca":
        block, rows, result = strategies.build_dca_block(
            close,
            ticker=args.ticker,
            contrib_months=args.contrib_months,
            hold_months=args.hold_months,
            asof=asof,
            label=args.label,
            gap=args.gap,
        )
        name = f"dca{args.contrib_months}-hold{args.hold_months}"
    else:
        close_b = me.fetch_close(args.ticker_b, args.start, args.end)
        block, rows, result = strategies.build_rebalance_block(
            close,
            close_b,
            ticker_a=args.ticker,
            ticker_b=args.ticker_b,
            asof=asof,
            weight_a=args.weight,
            hold_months=args.hold_months,
            intervals=tuple(args.interval_months),
            label_a=args.label,
            label_b=args.label_b,
            gap=args.gap,
        )
        name = f"reb{round(args.weight * 100)}-hold{args.hold_months}"

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"{_slug(args.ticker)}_{name}_{datetime.now():%Y%m%d-%H%M%S}"
    block_path = outdir / f"{stem}_block.txt"
    block_path.write_text(block, encoding="utf-8")

    print(f"시작 시점 {len(rows)}개")
    if args.strategy == "dca":
        if result["dca_win_ratio"] is not None:
            print(
                f"분할 매수가 앞선 비율: {result['dca_win_ratio']:.2f}% "
                f"({result['dca_wins']}/{result['count']})"
            )
    else:
        for months in args.interval_months:
            stat = result[months]["drawdown"]
            if stat is None:
                continue
            print(
                f"{strategies.interval_label(months)}: "
                f"수익 중앙값 {result[months]['return']['median']:.2f}% / "
                f"낙폭 중앙값 {stat['median']:.2f}%"
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
