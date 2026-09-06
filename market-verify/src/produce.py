"""검증을 통과한 대본으로 영상·썸네일을 만들고, 원하면 비공개로 올린다.

    python -m src.produce --script out/..._script.md
    python -m src.produce --script out/..._script.md --upload
"""

import argparse
import sys
import tempfile
from pathlib import Path

from src import render, script_parse, voice
from src.upload import UploadConfigError, check_credentials, upload

OUT_DIR = Path(__file__).resolve().parent.parent / "out"
DEFAULT_TAGS = ["주식", "지수", "과거데이터", "백테스트", "투자공부"]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="src.produce", description="대본 → 영상")
    parser.add_argument("--script", required=True, help="검증을 통과한 대본 .md 경로")
    parser.add_argument("--outdir", default=str(OUT_DIR))
    parser.add_argument("--voice", default=voice.DEFAULT_VOICE)
    parser.add_argument(
        "--silent",
        action="store_true",
        help="음성 없이 길이만 맞춘 무음으로 만든다. 화면 확인용이며 네트워크를 타지 않는다.",
    )
    parser.add_argument("--upload", action="store_true", help="유튜브에 올린다")
    parser.add_argument(
        "--privacy",
        default="private",
        choices=["private", "unlisted", "public"],
        help="기본은 비공개. 공개 전환은 눈으로 확인한 뒤 사람이 한다.",
    )
    return parser.parse_args(argv)


def _operator_note_filled(scenes):
    return any(scene.section.startswith("6.") for scene in scenes)


def build(script_text, outdir, stem, speak, voice_name, log=print):
    """장면을 만들고 영상과 썸네일을 낸다. 경로 두 개를 돌려준다."""
    scenes = script_parse.scenes(script_text)
    if not scenes:
        raise ValueError("대본에서 나레이션 구간을 찾지 못했다. 헤더 표기를 확인할 것.")

    titles = script_parse.titles(script_text)
    title = titles[0] if titles else stem
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    log(f"장면 {len(scenes)}개")
    if not _operator_note_filled(scenes):
        log("  ! [운영자 코멘트]가 비어 있다. 채우지 않으면 그 대목이 영상에서 빠진다.")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        audio_paths = voice.narrate(scenes, tmp, speak=speak, voice=voice_name)
        parts = []
        total = 0.0
        for index, (scene, audio) in enumerate(zip(scenes, audio_paths), start=1):
            image = render.slide(
                scene.screen_text, scene.section, tmp / f"slide_{index:03d}.png"
            )
            part = render.mux(image, audio, tmp / f"part_{index:03d}.mp4")
            seconds = render.audio_duration(audio)
            total += seconds
            parts.append(part)
            log(f"  {index:>2}/{len(scenes)} {scene.section} · {seconds:5.1f}초")

        video_path = outdir / f"{stem}.mp4"
        render.concat(parts, video_path, tmp)

    thumb_path = render.thumbnail(title, outdir / f"{stem}.jpg", subtitle="과거 사례 검증")
    log(f"영상 저장: {video_path}  ({total / 60:.1f}분)")
    log(f"썸네일 저장: {thumb_path}")
    return video_path, thumb_path


def main(argv=None):
    sys.stdout.reconfigure(line_buffering=True)
    args = parse_args(argv)

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"실패: 대본을 찾지 못했다: {script_path}")
        return 2
    script_text = script_path.read_text(encoding="utf-8")

    if args.upload:
        # 만들기 전에 본다. 다 만들고 나서 자격 증명이 없다고 하면 시간만 버린다.
        problem = check_credentials()
        if problem:
            print(f"실패: {problem}")
            return 2

    speak = voice.silent_speak if args.silent else voice.edge_tts_speak
    if args.silent:
        print("--silent: 무음으로 만든다. 화면 확인용이다.")

    try:
        video_path, thumb_path = build(
            script_text, args.outdir, script_path.stem.replace("_script", ""),
            speak, args.voice,
        )
    except Exception as error:
        print(f"실패: 영상을 만들지 못했다. {type(error).__name__}: {error}")
        return 3

    if not args.upload:
        print("업로드하지 않았다. 올리려면 --upload 를 붙일 것.")
        return 0

    try:
        video_id = upload(
            video_path,
            title=(script_parse.titles(script_text) or [script_path.stem])[0],
            description=script_parse.description(script_text),
            tags=DEFAULT_TAGS,
            privacy=args.privacy,
            thumbnail_path=thumb_path,
        )
    except UploadConfigError as error:
        print(f"실패: {error}")
        return 2
    except Exception as error:
        print(f"실패: 업로드하지 못했다. {type(error).__name__}: {error}")
        return 3

    print(f"업로드 완료({args.privacy}): https://youtu.be/{video_id}")
    if args.privacy == "private":
        print("비공개 상태다. 확인 후 유튜브 스튜디오에서 직접 공개로 바꿀 것.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
