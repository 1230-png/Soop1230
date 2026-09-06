"""데이터 블록 생성부터 대본 검증까지 한 번에 돌린다.

    python -m src.run --ticker ^GSPC --condition down-weeks --n 3 --start 1990-01-01
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from src import market_events as me
from src.writer import (
    APICallError,
    ScriptGenerationError,
    format_usage,
    write_script,
)

OUT_DIR = Path(__file__).resolve().parent.parent / "out"
KEY_ENV = "ANTHROPIC_API_KEY"
OPERATOR_HEADER = "## 6. [운영자 코멘트]"
# 저장할 때만 넣는 안내. 모델 출력에는 없고, 검증을 통과한 뒤에 붙는다.
# HTML 주석이라 유튜브 대본으로 옮길 때 화면에 남지 않는다.
OPERATOR_GUIDE = (
    "<!-- 여기에 운영자 본인의 관점을 직접 씁니다. 쓰고 나면 이 안내 줄은 지우세요.\n"
    "     위의 제목 줄은 지우지 마세요. 대본 구조가 매주 달라집니다.\n"
     "     면책 문구는 이미 유튜브 설명란에 들어가 있으니 여기 또 쓸 필요는 없습니다. -->"
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="src.run", description="과거 사례 검증 대본 생성")
    parser.add_argument("--ticker", required=True, help="예: ^GSPC, ^VIX, BTC-USD")
    parser.add_argument(
        "--condition",
        required=True,
        choices=["down-weeks", "drawdown", "threshold"],
        help="down-weeks: 주간 연속 하락 / drawdown: 전고점 대비 하락 / threshold: 임계값 돌파",
    )
    parser.add_argument("--n", type=int, default=3, help="down-weeks: 연속 하락 주 수")
    parser.add_argument("--pct", type=float, default=10.0, help="drawdown: 전고점 대비 하락률")
    parser.add_argument("--level", type=float, help="threshold: 돌파 기준값")
    parser.add_argument("--start", required=True, help="조회 시작일 YYYY-MM-DD")
    parser.add_argument("--end", help="조회 종료일 YYYY-MM-DD")
    parser.add_argument("--label", help="대상 표기용 이름. 예: S&P 500")
    parser.add_argument("--outdir", default=str(OUT_DIR))
    parser.add_argument(
        "--block-only",
        action="store_true",
        help="데이터 블록만 만들고 API를 호출하지 않는다.",
    )
    args = parser.parse_args(argv)
    if args.condition == "threshold" and args.level is None:
        parser.error("--condition threshold 에는 --level 이 필요하다.")
    return args


def resolve_events(close, args):
    """조건 시점 목록과 블록에 적을 조건 문구를 돌려준다."""
    if args.condition == "down-weeks":
        return me.down_weeks(close, n=args.n), f"주간 종가 {args.n}주 연속 하락"
    if args.condition == "drawdown":
        return (
            me.drawdown_entry(close, pct=args.pct),
            f"전고점 대비 {args.pct:g}% 하락 구간 첫 진입",
        )
    return (
        me.threshold_break(close, args.level),
        f"{args.level:g} 이상 첫 돌파",
    )


def add_operator_guide(script):
    """운영자 칸에 작성 안내를 넣어 저장한다.

    빈 칸만 남겨 두면 무엇을 어떻게 쓰라는 건지 알 수 없어
    제목 줄을 지우고 그 자리에 쓰게 된다. 실제로 그런 일이 있었다.
    """
    if OPERATOR_HEADER not in script:
        return script
    return script.replace(
        OPERATOR_HEADER, f"{OPERATOR_HEADER}\n{OPERATOR_GUIDE}", 1
    )


def check_api_key(env=None):
    """호출 전에 키 형태를 본다. 문제가 없으면 None.

    터미널에 붙여넣을 때 이스케이프 문자가 섞여 들어가는 일이 잦다.
    그대로 요청을 보내면 서버가 400 만 돌려줘 원인을 찾기 어렵다.
    """
    key = (os.environ if env is None else env).get(KEY_ENV, "")
    if not key:
        return f"{KEY_ENV} 가 설정되지 않았다. export {KEY_ENV}='sk-ant-...' 로 넣을 것."
    if any(ch in key for ch in "\x1b\r\n\t "):
        return (
            f"{KEY_ENV} 에 공백이나 제어문자가 섞여 있다. "
            "터미널 붙여넣기가 이스케이프 문자를 끼워 넣은 경우다. 다시 설정할 것."
        )
    if not key.startswith("sk-ant-"):
        return f"{KEY_ENV} 가 sk-ant- 로 시작하지 않는다. 값이 잘못됐다."
    return None


def _slug(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "", text) or "ticker"


def main(argv=None):
    # 파일로 넘길 때 파이썬이 출력을 모아두는 바람에 진행 상황이 안 보인다.
    # 몇 분 걸리는 작업이라 멈춘 것처럼 보인다. 줄 단위로 바로 내보낸다.
    sys.stdout.reconfigure(line_buffering=True)
    args = parse_args(argv)

    close = me.fetch_close(args.ticker, args.start, args.end)
    dates, condition = resolve_events(close, args)
    block, rows, _ = me.build_block(
        close, dates, ticker=args.ticker, condition=condition, asof=None, label=args.label
    )

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"{_slug(args.ticker)}_{args.condition}_{datetime.now():%Y%m%d-%H%M%S}"
    block_path = outdir / f"{stem}_block.txt"
    block_path.write_text(block, encoding="utf-8")

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
        # 실패해도 토큰은 나갔다. 얼마 썼는지 남긴다.
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
