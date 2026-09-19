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
    brand, news_topics, operator_note, produce, recap, run, run_macro,
    run_recap, run_strategy, run_tokenomics, script_parse, shorts, topics,
    upload, voice, writer,
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
        "--shorts-max-seconds", type=float, default=shorts.MAX_SHORT_SECONDS,
        help="숏폼 한 편의 길이 상한(초). 넘치면 뒤 장면을 뺀다.",
    )
    parser.add_argument(
        "--upload", action="store_true",
        help="만든 영상을 유튜브에 올린다. 기본은 올리지 않는다.",
    )
    parser.add_argument(
        "--privacy", default="private", choices=upload.PRIVACY_CHOICES,
        help="업로드 공개 범위. 기본은 비공개.",
    )
    parser.add_argument(
        "--no-operator-note", action="store_true",
        help="운영자 코멘트를 자동으로 채우지 않는다. 사람이 직접 쓸 때 쓴다.",
    )
    parser.add_argument(
        "--log-path", default=str(topics.LOG_PATH), help="토픽 사용 기록 CSV 경로"
    )
    parser.add_argument(
        "--repeat", type=int, default=1,
        help="한 번 실행에 만들 편수. 편마다 다음 토픽으로 넘어간다.",
    )
    parser.add_argument(
        "--source", default="news", choices=["news", "pool", "week", "month"],
        help="news: 어제 크게 움직인 자산에서 소재를 고른다(움직임이 없으면 pool). "
             "pool: 순환 풀에서만 고른다. "
             "week/month: 새 소재를 쓰지 않고 이번 주·이번 달 회차를 묶는다(몰아보기).",
    )
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat 는 1 이상이어야 한다.")
    if args.repeat > 1 and args.topic_key:
        # 같은 토픽을 여러 번 만들어 봐야 같은 영상이 나온다.
        parser.error("--topic-key 는 한 편만 만들 때 쓴다. --repeat 와 함께 쓸 수 없다.")
    if args.source in recap.WINDOWS:
        # 한 구간은 한 편이다. 두 번 만들면 같은 편이 두 번 올라간다.
        if args.repeat > 1:
            parser.error(f"--source {args.source} 는 한 구간에 한 편이다. --repeat 를 쓸 수 없다.")
        if args.topic_key:
            parser.error(f"--source {args.source} 는 소재를 새로 고르지 않는다. --topic-key 를 쓸 수 없다.")
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
    if args.upload:
        # 만들기 전에 본다. 5분 걸려 만들고 나서 자격 증명이 없다고 하면 그 시간이 버려진다.
        problem = upload.check_credentials()
        if problem:
            print(f"실패: {problem}")
            return 2

    if args.source in recap.WINDOWS:
        # 몰아보기. 새 소재를 고르지 않고 이번 구간에 이미 낸 회차를 묶는다.
        # 여기가 소재 반복 금지의 예외다 — 이유는 src/recap.py 머리말에.
        topic = topics.Topic(
            recap.window_key(args.source), recap.RECAP_TOOL, (),
            f"{run_recap.WINDOW_LABEL[args.source]} 몰아보기",
        )
        try:
            script_path = run_recap.build(
                args.source, args.outdir, args.log_path,
                block_only=args.block_only,
            )
        except writer.ScriptGenerationError as error:
            print(f"실패: {error.attempts}회 모두 검증을 통과하지 못했다.")
            print(writer.format_usage(error.usages))
            return 1
        except writer.APICallError as error:
            print(f"실패: API 를 호출하지 못했다. {error}")
            return 3
        if script_path is None:
            # 묶을 것이 없거나 --block-only 다. 둘 다 실패가 아니다.
            # **여기서 _latest_script 로 넘어가면 안 된다** — outdir 에 남은
            # 지난 회차 대본을 새로 만든 것으로 착각해 다시 발행한다.
            return 0
    else:
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

    # 검증이 끝난 뒤다. 작성 루프는 이 칸을 비운 채로 내놓아야 하고 검증기도 그대로
    # 그걸 요구한다 — 여기서 채우는 것은 사람이 손으로 쓰던 자리를 대신하는 것이다.
    if not args.no_operator_note:
        filled = operator_note.fill(script_text)
        if filled != script_text:
            script_text = filled
            script_path.write_text(script_text, encoding="utf-8")

    speak = voice.silent_speak if args.silent else voice.edge_tts_speak

    # 몰아보기는 분포 그림을 그리지 않는다. 묶은 블록에는 사례 표가 조건마다
    # 하나씩 들어 있는데 chart.parse_cases 는 **첫 표에서 멈춘다.** 그대로
    # 넘기면 2번·3번 조건을 읽는 동안 1번 조건 그림이 떠 있게 된다 — 대본이
    # 말하는 값과 화면에 보이는 값이 갈라지는, 이 파이프라인이 제일 피하는 일이다.
    # 전략·토크노믹스 블록처럼 글자 화면으로 돌아간다.
    block_text = None if args.source in recap.WINDOWS else produce.block_beside(script_path)
    if block_text is None and args.source in recap.WINDOWS:
        print("  몰아보기라 분포 그림 없이 글자 화면으로 간다(조건마다 표가 달라서다).")

    video_path, thumb_path = produce.build(
        script_text, args.outdir, stem, speak, args.voice,
        block_text=block_text,
    )

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
                shorts.build(
                    script_text, args.outdir, stem, speak, args.voice, index,
                    max_seconds=args.shorts_max_seconds,
                )
            )
        except shorts.CutNotFoundError as error:
            print(f"  ! 숏폼 컷 {index + 1}번 건너뜀: {error}")

    if limit and not short_paths:
        # 컷은 읽었는데 한 편도 못 만들었다. 인용문이 본문과 어긋난 것이다.
        # 위 건너뜀 줄이 로그에 묻히기 쉬워 한 번 더 못을 박는다.
        print("  ! 숏폼 컷을 읽었는데 한 편도 만들지 못했다. 인용문이 본문과 다르다 — 대본을 확인할 것.")

    topics.record_topic(topic, args.log_path)
    print(f"완료 — 롱폼 1개, 숏폼 {len(short_paths)}개.")
    print(f"  롱폼: {video_path}")
    for path in short_paths:
        print(f"  숏폼: {path}")

    if not args.upload:
        print("업로드하지 않았다. 올리려면 --upload 를 붙일 것.")
        return 0
    return upload_all(script_text, video_path, thumb_path, short_paths, args)


def short_title(base_title, index):
    """숏폼 제목. #Shorts 가 붙어야 유튜브가 숏폼으로 잡는다.

    제목은 100자까지다. #Shorts 자리를 남겨 두고 자른다 — 뒤에서 잘리면 태그가
    통째로 날아가고, 그러면 세로 영상이 일반 영상으로 올라간다.
    """
    suffix = f" ({index}) #Shorts"
    return base_title[: 100 - len(suffix)].rstrip() + suffix


# 유튜브 일일 할당량은 **구글 클라우드 프로젝트** 단위다. 채널 단위가 아니다.
# 한 프로젝트를 여러 채널이 나눠 쓰면 서로의 할당량을 깎는다. 업로드 한 편이
# 1,600 units, 기본 할당량이 10,000 이라 하루 6편이 한계다.
# 이 저장소는 채널을 여럿 굴린다 — market-verify 는 프로젝트를 따로 쓰는 편이 낫다.
QUOTA_MARKERS = ("quotaexceeded", "dailylimitexceeded", "quota exceeded")
QUOTA_HINT = """    할당량은 구글 클라우드 프로젝트 단위다(채널 단위가 아니다). 이 저장소는
    채널을 여럿 굴리므로, 한 프로젝트를 같이 쓰면 서로의 몫을 깎는다.
    다음 날 자동으로 초기화된다. 매일 모자라면 market-verify 용 프로젝트를
    따로 만들어 MV_* 를 그쪽 것으로 바꿀 것."""


def is_quota_error(error):
    """할당량이 떨어져서 난 실패인지. 문구로 본다.

    googleapiclient 는 HttpError 하나로 온갖 것을 돌려준다. 예외 타입만 보면
    할당량인지 권한인지 잘못된 파일인지 구분되지 않는다.
    """
    return any(marker in str(error).lower() for marker in QUOTA_MARKERS)


def upload_all(script_text, video_path, thumb_path, short_paths, args):
    """롱폼과 숏폼을 올린다. 하나가 실패해도 나머지는 계속 올린다.

    한 편이 막혔다고 그날 발행이 통째로 없어지는 것이 더 나쁘다. 무엇이 올라갔고
    무엇이 안 올라갔는지는 마지막에 모아 찍는다.
    """
    titles = script_parse.titles(script_text)
    base_title = titles[0] if titles else Path(video_path).stem
    description = brand.video_description(script_parse.description(script_text))

    jobs = [(video_path, base_title, thumb_path)]
    jobs += [
        (path, short_title(base_title, index), None)
        for index, path in enumerate(short_paths, start=1)
    ]

    uploaded, failed = [], []
    for index, (path, title, thumb) in enumerate(jobs):
        try:
            video_id = upload.upload(
                path, title=title, description=description, tags=brand.TAGS,
                privacy=args.privacy, thumbnail_path=thumb,
            )
        except Exception as error:
            print(f"  ! 올리지 못했다({Path(path).name}): {type(error).__name__}: {error}")
            failed.append(path)
            if is_quota_error(error):
                # 할당량이 떨어졌으면 남은 것도 전부 떨어진다. 계속 두드려봐야
                # 같은 에러가 쌓일 뿐이다.
                remaining = len(jobs) - index - 1
                print(
                    f"  ! 오늘 할당량이 떨어졌다. 남은 {remaining}편은 시도하지 않는다.\n"
                    f"{QUOTA_HINT}"
                )
                failed.extend(job[0] for job in jobs[index + 1:])
                break
            continue
        print(f"  올림({args.privacy}): {title} — https://youtu.be/{video_id}")
        uploaded.append(video_id)

    print(f"업로드 — 성공 {len(uploaded)}개, 실패 {len(failed)}개.")
    if args.privacy == "private":
        print("비공개 상태다. 확인 후 유튜브 스튜디오에서 공개로 바꿀 것.")
    # 하나도 못 올렸으면 실패다. 로그만 보고 올라간 줄 알면 안 된다.
    return 0 if uploaded else 4


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
