"""매크로 지표 조건이 성립했던 시점 이후 자산이 어떻게 움직였는지 대본으로 만든다.

    python -m src.run_macro --series T10Y2Y --below 0 \
        --ticker ^GSPC --label 'S&P 500' --start 1990-01-01 --block-only

지표는 FRED, 결과는 야후에서 받는다. 검증기·작성기·영상 파이프라인은 그대로 쓴다.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from src import macro
from src import market_events as me
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
        prog="src.run_macro", description="매크로 지표 조건 이후 자산 분포"
    )
    parser.add_argument("--series", required=True, help="FRED 시리즈 ID. 예: T10Y2Y, M2SL")
    parser.add_argument("--ticker", required=True, help="결과를 잴 자산. 예: ^GSPC")
    parser.add_argument("--label", help="자산 표기용 이름. 예: S&P 500")
    parser.add_argument("--start", required=True, help="조회 시작일 YYYY-MM-DD")
    parser.add_argument("--end", help="조회 종료일 YYYY-MM-DD")
    threshold = parser.add_mutually_exclusive_group(required=True)
    threshold.add_argument("--above", type=float, help="지표가 이 값 이상으로 처음 올라선 시점")
    threshold.add_argument("--below", type=float, help="지표가 이 값 이하로 처음 내려간 시점")
    parser.add_argument(
        "--yoy",
        type=int,
        metavar="PERIODS",
        help="원값 대신 전년 대비 변화율(%%)에 조건을 건다. 월간 지표는 12.",
    )
    parser.add_argument("--outdir", default=str(OUT_DIR))
    parser.add_argument(
        "--block-only", action="store_true", help="데이터 블록만 만들고 대본 API 를 호출하지 않는다."
    )
    return parser.parse_args(argv)


def resolve_condition(series, args):
    """조건 시점 목록과 블록에 적을 조건 문구."""
    name = macro.series_name(args.series)
    if args.yoy:
        series = macro.yoy_change(series, args.yoy)
        subject = f"{name} 전년 대비 변화율"
        unit = "%"
    else:
        subject = name
        unit = ""

    if args.above is not None:
        return macro.cross_above(series, args.above), (
            f"{subject}가 {args.above:g}{unit} 이상으로 처음 올라선 시점"
        ), series
    return macro.cross_below(series, args.below), (
        f"{subject}가 {args.below:g}{unit} 이하로 처음 내려간 시점"
    ), series


def main(argv=None):
    sys.stdout.reconfigure(line_buffering=True)
    args = parse_args(argv)

    fred_problem = macro.check_api_key()
    if fred_problem:
        print(f"실패: {fred_problem}")
        return 2

    try:
        raw = macro.fetch_series(args.series, args.start, args.end)
    except macro.FredError as error:
        print(f"실패: {error}")
        return 3

    close = me.fetch_close(args.ticker, args.start, args.end)
    dates, condition, used = resolve_condition(raw, args)

    block, rows, _ = macro.build_block(
        macro=used,
        close=close,
        series_id=args.series,
        ticker=args.ticker,
        condition=condition,
        event_dates=dates,
        asof=datetime.now().strftime("%Y-%m-%d"),
        label=args.label,
    )

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = (
        f"{_slug(args.series)}_{_slug(args.ticker)}"
        f"_{datetime.now():%Y%m%d-%H%M%S}"
    )
    block_path = outdir / f"{stem}_block.txt"
    block_path.write_text(block, encoding="utf-8")

    print(f"조건: {condition}")
    print(f"사례 수: {len(rows)}")
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
