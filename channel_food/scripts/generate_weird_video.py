"""'현실 속 기괴한 현상' 쇼츠 1편을 생성한다.

각 나레이션 구간의 실제 길이를 ffprobe로 재서 슬라이드 표시 시간과 맞추므로,
화면의 문장과 들리는 문장이 어긋나지 않는다.

전부 무료 스택: Pillow(이미지), edge-tts(음성), ffmpeg(앰비언스 합성 및 먹싱).

환경 변수:
  AUDIO_MODE          narration | narration_ambience   (기본: narration)
  SKIP_DAILY_GUARD    1이면 일일 업로드 한도 검사를 건너뛴다 (샘플 생성용)
  OUTPUT_PREFIX       출력 파일 접두사 (기본: weird_shorts)
"""

import csv
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import ImageDraw, ImageFont

import brand
import common

ROOT = Path(__file__).resolve().parent.parent
CONTENT_BANK = ROOT / "scripts" / "weird_content.json"
USED_LOG = ROOT / "used_log.csv"
OUTPUT_DIR = ROOT / "output"

LOG_FIELDS = ["date", "content_id", "type", "title", "video_path", "youtube_video_id", "status"]

# 구간 사이에 넣는 짧은 정적. 문장이 붙어 들리는 걸 막는다.
SEGMENT_GAP_SEC = 0.35

# ffprobe가 길이를 못 재면 0.0을 돌려준다. 그대로 쓰면 슬라이드가 스쳐 지나가
# 읽을 수 없으므로 최소 표시 시간을 보장한다.
MIN_SEGMENT_SEC = 1.8


def load_content():
    with open(CONTENT_BANK, "r", encoding="utf-8") as f:
        return json.load(f)


def get_used_ids() -> set:
    """업로드까지 끝난 content_id 집합.

    status가 uploaded인 행만 센다. 생성은 됐지만 업로드가 막힌 편
    (일일 한도, 할당량 초과, 인증 실패 등)을 소진 처리해 버리면
    그 콘텐츠가 영영 방송되지 않는다.

    로그가 손상돼 읽히지 않으면 예외를 그대로 올린다. 조용히 빈 집합을
    돌려주면 이미 올린 콘텐츠를 중복 생성하게 된다.
    """
    if not USED_LOG.exists():
        return set()

    used = set()
    with open(USED_LOG, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            raw = (row.get("content_id") or "").strip()
            if raw and row.get("status") == "uploaded":
                used.add(int(raw))
    return used


def pick_unused_content():
    """아직 안 쓴 것 중 가장 작은 id를 고른다.

    무작위 대신 순차 선택이라 어떤 편이 다음에 나올지 예측 가능하고,
    한 바퀴를 다 돌기 전에 같은 편이 다시 나오지 않는다.
    """
    content = load_content()
    used = get_used_ids()
    available = [c for c in content if c["id"] not in used]

    if not available:
        print("[안내] 모든 콘텐츠를 한 바퀴 사용했습니다. 처음부터 다시 시작합니다.", file=sys.stderr)
        available = content

    return min(available, key=lambda c: c["id"])


def narration_segments(item) -> list:
    """화면에 띄울 문장과 읽어 줄 문장을 1:1로 짝지어 돌려준다."""
    segments = [("hook", item["hook"])]
    segments += [("body", line) for line in item["body"]]
    segments.append(("twist", item["twist"]))
    return segments


def make_slide(item, role: str, text: str, index: int, photo_path=None):
    """구간 하나에 대응하는 세로 슬라이드 한 장.

    photo_path가 있으면 사진을 배경으로 깔고, 없으면 그라데이션으로 되돌아간다.
    팔레트는 구간마다 조금씩 다르게 골라, 같은 사진이라도 화면이 미세하게 변한다.
    """
    palette = common.pick_palette(f"{item['id']}-{index}", common.WEIRD_PALETTES)
    if photo_path is not None:
        img = common.make_photo_background(photo_path, *palette)
    else:
        img = common.make_background(*palette)
    draw = ImageDraw.Draw(img)
    font_path = common.find_korean_font()

    if role == "hook":
        font = ImageFont.truetype(font_path, 78)
        fill, wrap, y = (255, 255, 255), 13, 620
    elif role == "twist":
        font = ImageFont.truetype(font_path, 70)
        fill, wrap, y = (232, 196, 120), 14, 660
    else:
        font = ImageFont.truetype(font_path, 60)
        fill, wrap, y = (226, 230, 238), 16, 700

    common.draw_centered(draw, text, font, y, fill=fill, wrap_width=wrap, line_gap=24)

    # 하단 채널 표기. 재업로드/도용 시 출처가 남는다.
    footer_font = ImageFont.truetype(font_path, 38)
    common.draw_centered(
        draw, brand.CHANNEL_HANDLE, footer_font, common.HEIGHT - 190,
        fill=(120, 126, 140), wrap_width=30, line_gap=10,
    )
    return img


def build_audio(item, segments, audio_mode: str):
    """구간별 TTS를 만들어 하나로 잇고, (오디오 경로, 구간별 길이)를 돌려준다."""
    seg_paths, seg_durations = [], []

    for i, (_role, text) in enumerate(segments):
        seg_path = OUTPUT_DIR / f"seg_{item['id']}_{i}.mp3"
        common.tts_save_segment("ko", text, seg_path, use_elevenlabs_for_en=False)

        gap_path = OUTPUT_DIR / f"gap_{item['id']}_{i}.mp3"
        common.generate_silence(SEGMENT_GAP_SEC, gap_path)

        seg_paths += [seg_path, gap_path]
        spoken = common.probe_duration(seg_path)
        if spoken <= 0:
            print(f"  [경고] {i}번 구간 길이를 재지 못해 기본값을 씁니다.", file=sys.stderr)
        seg_durations.append(max(spoken + SEGMENT_GAP_SEC, MIN_SEGMENT_SEC))

    narration_path = OUTPUT_DIR / f"narration_{item['id']}.mp3"
    common.concat_audio(seg_paths, narration_path)
    for part in seg_paths:
        part.unlink(missing_ok=True)

    if audio_mode != "narration_ambience":
        return narration_path, seg_durations

    total = sum(seg_durations)
    ambience_path = OUTPUT_DIR / f"ambience_{item['id']}.mp3"
    if common.mix_ambience(item.get("ambience", []), total, ambience_path) is None:
        print("  [안내] 앰비언스를 만들지 못해 나레이션만 사용합니다.", file=sys.stderr)
        return narration_path, seg_durations

    mixed_path = OUTPUT_DIR / f"audio_{item['id']}.mp3"
    common.mix_narration_with_ambience(narration_path, ambience_path, mixed_path)
    narration_path.unlink(missing_ok=True)
    ambience_path.unlink(missing_ok=True)
    return mixed_path, seg_durations


def build_video(item, slide_paths, durations, audio_path, out_path: Path) -> Path:
    concat_list = OUTPUT_DIR / f"concat_{item['id']}.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for path, dur in zip(slide_paths, durations):
            f.write(f"file '{path}'\n")
            f.write(f"duration {dur:.3f}\n")
        # concat demuxer는 마지막 duration을 무시하므로 마지막 장을 한 번 더 적는다.
        f.write(f"file '{slide_paths[-1]}'\n")

    silent_path = OUTPUT_DIR / f"{out_path.stem}_silent.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-vf", "scale=1080:1920,fps=30", "-pix_fmt", "yuv420p",
         "-c:v", "libx264", "-crf", "23", str(silent_path)],
        check=True, capture_output=True,
    )

    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(silent_path), "-i", str(audio_path),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-map", "0:v:0", "-map", "1:a:0", "-shortest", str(out_path)],
        check=True, capture_output=True,
    )

    silent_path.unlink(missing_ok=True)
    concat_list.unlink(missing_ok=True)
    for path in slide_paths:
        path.unlink(missing_ok=True)
    audio_path.unlink(missing_ok=True)
    return out_path


def make_metadata(item) -> dict:
    tags = brand.BASE_HASHTAGS + item.get("hashtags", [])
    description = f"""{item['hook']}

{item['twist']}

{brand.CHANNEL_FOOTER}

{' '.join(tags)}
"""
    return {
        "title": item["title"],
        "description": description,
        # YouTube 태그는 '#' 없이 넣어야 한다. '#'는 설명문에서만 해시태그로 동작한다.
        "tags": [t.lstrip("#") for t in tags],
        "category_id": "24",  # Entertainment
        "make_for_kids": False,
    }


def log_usage(item, video_path: Path) -> None:
    is_new = not USED_LOG.exists()
    with open(USED_LOG, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "date": datetime.datetime.now().isoformat(),
            "content_id": item["id"],
            "type": item["type"],
            "title": item["title"],
            "video_path": str(video_path),
            "youtube_video_id": "",
            "status": "generated",
        })


def main() -> int:
    OUTPUT_DIR.mkdir(exist_ok=True)
    audio_mode = os.environ.get("AUDIO_MODE", "narration")
    prefix = os.environ.get("OUTPUT_PREFIX", "weird_shorts")

    # 영상을 만들기 전에 먼저 막는다. GitHub Actions 빌드 시간을 아끼기 위해서다.
    if os.environ.get("SKIP_DAILY_GUARD") != "1" and common.daily_quota_exhausted(USED_LOG):
        print(
            f"[중단] 오늘 이미 {common.MAX_DAILY_UPLOADS}편을 처리했습니다. "
            "영상을 만들지 않고 종료합니다.",
            file=sys.stderr,
        )
        print(json.dumps({"skipped": True, "reason": "daily_limit"}, ensure_ascii=False))
        return 0

    item = pick_unused_content()
    segments = narration_segments(item)
    print(f"[생성] #{item['id']} {item['title']}  ({audio_mode}, {len(segments)}구간)", file=sys.stderr)

    audio_path, durations = build_audio(item, segments, audio_mode)

    # 배경 사진은 영상당 한 장만 받아 모든 슬라이드가 공유한다.
    # 호출을 1회로 묶어 Pexels 무료 한도(시간당 200회)에 여유를 둔다.
    photo_path = None
    query = item.get("image_query", "")
    if query:
        candidate = OUTPUT_DIR / f"bg_{item['id']}.jpg"
        photo_path = common.fetch_background_photo(query, candidate)

    slide_paths = []
    for i, (role, text) in enumerate(segments):
        slide_path = OUTPUT_DIR / f"slide_{item['id']}_{i}.png"
        make_slide(item, role, text, i, photo_path).save(slide_path)
        slide_paths.append(slide_path)

    video_path = OUTPUT_DIR / f"{prefix}_{item['id']}.mp4"
    build_video(item, slide_paths, durations, audio_path, video_path)
    if photo_path is not None:
        photo_path.unlink(missing_ok=True)

    metadata_path = OUTPUT_DIR / f"metadata_{item['id']}.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(make_metadata(item), f, ensure_ascii=False, indent=2)

    log_usage(item, video_path)

    print(f"[완료] {video_path}  ({sum(durations):.1f}초)", file=sys.stderr)
    print(json.dumps({
        "skipped": False,
        "video_path": str(video_path),
        "metadata_path": str(metadata_path),
        "content_id": item["id"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
