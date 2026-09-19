"""검증을 통과한 대본으로 영상·썸네일을 만들고, 원하면 비공개로 올린다.

    python -m src.produce --script out/..._script.md
    python -m src.produce --script out/..._script.md --upload
"""

import argparse
import sys
import tempfile
from pathlib import Path

from src import brand, chart, render, script_parse, voice
from src.upload import UploadConfigError, check_credentials, upload

OUT_DIR = Path(__file__).resolve().parent.parent / "out"
# 분포 그림을 쓰는 구간. 수치가 나오는 자리는 여기다.
CHART_SECTION = "4."


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


def block_beside(script_path):
    """대본 옆의 데이터 블록. run.py 가 같은 stem 으로 써 둔다. 없으면 None."""
    script_path = Path(script_path)
    stem = script_path.stem.replace("_script", "")
    path = script_path.with_name(f"{stem}_block.txt")
    return path.read_text(encoding="utf-8") if path.exists() else None


def _operator_note_filled(scenes):
    return any(scene.section.startswith("6.") for scene in scenes)


def _scene_image(scene, series, out_path, log):
    """결과 구간에는 분포 그림을, 나머지에는 글자 화면을 쓴다.

    그림을 못 그리면 글자 화면으로 돌아간다. 사람 확인 없이 공개로 나가는
    자리라, 그림 하나 때문에 그날 영상이 통째로 안 나오면 안 된다. 다만 조용히
    넘어가지는 않는다 — 그림이 매일 빠지고 있는데 모르는 쪽이 더 나쁘다.
    """
    if series and scene.section.startswith(CHART_SECTION):
        try:
            return render.distribution_slide(
                series, scene.screen_text, scene.section, out_path
            )
        except Exception as error:
            log(f"  ! 분포 그림 실패({type(error).__name__}: {error}). 글자 화면으로 간다.")
    return render.slide(scene.screen_text, scene.section, out_path)


def build(script_text, outdir, stem, speak, voice_name, log=print, block_text=None):
    """장면을 만들고 영상과 썸네일을 낸다. 경로 두 개를 돌려준다.

    block_text 를 주면 결과 구간을 분포 그림으로 그린다. 숫자는 블록에 적힌 것을
    그대로 읽어 쓴다 — 대본이 말하는 값과 그림이 보여 주는 값이 갈라지면 안 된다.
    """
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

    series = chart.parse_cases(block_text) if block_text else []
    if series:
        log(f"  분포 그림: 구간 {len(series)}개 · 사례 {len(series[0][1])}건")
    elif block_text:
        log("  분포 그림 없음 — 이 블록에는 사례별 표가 없다(전략·토크노믹스).")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        audio_paths = voice.narrate(scenes, tmp, speak=speak, voice=voice_name, log=log)
        parts = []
        total = 0.0
        for index, (scene, audio) in enumerate(zip(scenes, audio_paths), start=1):
            image = _scene_image(scene, series, tmp / f"slide_{index:03d}.png", log)
            # 길이를 먼저 잰다. mux 가 이 길이로 확대 프레임 수를 잡는다.
            seconds = render.audio_duration(audio)
            part = render.mux(image, audio, tmp / f"part_{index:03d}.mp4", seconds=seconds)
            total += seconds
            parts.append(part)
            log(f"  {index:>2}/{len(scenes)} {scene.section} · {seconds:5.1f}초")

        video_path = outdir / f"{stem}.mp4"
        render.concat(parts, video_path, tmp)

    thumb_path = render.thumbnail(
        title, outdir / f"{stem}.jpg", subtitle=brand.NAME, series=series
    )
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
            speak, args.voice, block_text=block_beside(script_path),
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
            description=brand.video_description(script_parse.description(script_text)),
            tags=brand.TAGS,
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
