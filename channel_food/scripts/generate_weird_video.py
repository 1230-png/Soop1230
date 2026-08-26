"""'현실 속 기괴한 현상' 쇼츠 1편을 생성한다.

전부 무료 스택: Pillow(이미지), edge-tts(음성), ffmpeg(앰비언스 합성 및 먹싱).

세 가지가 영상 형태를 결정한다:

1. **길이는 나레이션을 따른다.** 30초 고정이 아니다. 문장별 TTS 길이를
   ffprobe로 재서 슬라이드 표시 시간과 맞추므로, 화면의 문장과 들리는 문장이
   어긋나지 않는다.
2. **첫 3초는 0.5초마다 화면이 바뀐다.** 쇼츠 이탈은 대부분 앞 3초에서 난다.
   이 구간만 문장 경계를 무시하고 배경을 조금씩 확대하며 끊는다 (timeline.py).
3. **마지막은 질문으로 끝난다.** 반전 문장으로 끝나면 시청자가 할 일이 없다 (cta.py).

주제 선택에는 feedback.py의 판정이 들어간다. 실적이 나쁜 주제는 건너뛴다.

환경 변수:
  AUDIO_MODE          narration | narration_ambience   (기본: narration)
  SKIP_DAILY_GUARD    1이면 일일 업로드 한도 검사를 건너뛴다 (샘플 생성용)
  OUTPUT_PREFIX       출력 파일 접두사 (기본: weird_shorts)
  HOOK_SEC / HOOK_CUT 빠른 컷 구간 길이와 간격 (기본: 3.0 / 0.5)
"""

import csv
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import brand
import common
import cta
import feedback
from timeline import build_timeline, total_duration

ROOT = Path(__file__).resolve().parent.parent
CONTENT_BANK = ROOT / "scripts" / "weird_content.json"
USED_LOG = ROOT / "used_log.csv"
METRICS_LOG = ROOT / "metrics.csv"
OUTPUT_DIR = ROOT / "output"

LOG_FIELDS = ["date", "content_id", "type", "title", "video_path", "youtube_video_id", "status"]

# 구간 사이에 넣는 짧은 정적. 문장이 붙어 들리는 걸 막는다.
SEGMENT_GAP_SEC = 0.35

# ffprobe가 길이를 못 재면 0.0을 돌려준다. 그대로 쓰면 슬라이드가 스쳐 지나가
# 읽을 수 없으므로 최소 표시 시간을 보장한다. 이때는 정적도 함께 늘려
# 오디오와 영상 길이가 어긋나지 않게 한다.
MIN_SEGMENT_SEC = 1.8

# 앞 3초 빠른 컷.
HOOK_SEC = float(os.environ.get("HOOK_SEC", "3.0"))
HOOK_CUT = float(os.environ.get("HOOK_CUT", "0.5"))

# 배경 변형 수 상한. 사진 한 장을 확대해 만드므로 너무 늘리면 화질이 떨어진다.
MAX_VARIANTS = 12
ZOOM_STEP = 0.035

# 남은 편이 이 수 이하로 떨어지면 미리 경고한다. 소진된 뒤에 알면 늦다.
LOW_STOCK_WARNING = 5


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
    """아직 안 쓴 것 중 가장 작은 id를 고른다. 없으면 None.

    실적이 나쁜 주제(feedback.failing_types)는 건너뛴다. 단, 남은 것이
    전부 그 주제뿐이면 그냥 쓴다 — 피드백 때문에 발행이 멈추면 안 된다.
    판정에 필요한 표본이 쌓이기 전에는 제외 목록이 비어 있고, 이때는
    예전과 똑같이 순서대로 나간다. 채널 초기에는 정상이다.

    소진돼도 처음으로 되돌아가지 않는다 — 같은 영상을 다시 올리면 채널에
    중복이 쌓인다. 대신 아무것도 올리지 않고 멈춘다.
    """
    content = load_content()
    used = get_used_ids()
    available = [c for c in content if c["id"] not in used]

    if not available:
        return None

    if len(available) <= LOW_STOCK_WARNING:
        print(
            f"[경고] 남은 콘텐츠가 {len(available)}편뿐입니다. "
            "weird_content.json에 새 시나리오를 추가하세요.",
            file=sys.stderr,
        )

    excluded = feedback.failing_types(METRICS_LOG, USED_LOG)
    if excluded:
        preferred = [c for c in available if c.get("type") not in excluded]
        if preferred:
            print(f"[피드백] 실적이 나쁜 주제를 건너뜁니다: {', '.join(sorted(excluded))}",
                  file=sys.stderr)
            available = preferred
        else:
            print(
                f"[피드백] 제외 대상({', '.join(sorted(excluded))}) 외에 남은 콘텐츠가 없어 "
                "그대로 진행합니다.",
                file=sys.stderr,
            )

    return min(available, key=lambda c: c["id"])


def narration_segments(item) -> list:
    """화면에 띄울 문장과 읽어 줄 문장을 1:1로 짝지어 돌려준다."""
    segments = [("hook", item["hook"])]
    segments += [("body", line) for line in item["body"]]
    segments.append(("twist", item["twist"]))
    segments.append(("cta", cta.pick(item)))
    return segments


def build_backgrounds(item, count: int, photo_path=None):
    """컷마다 쓸 배경을 만든다.

    사진이 있으면 무거운 합성(블러·리사이즈·틴트)을 한 번만 하고 크롭만 달리한다.
    변형마다 make_photo_background를 부르면 같은 작업을 열 번 넘게 반복하게 된다.
    앞 3초에서 0.5초마다 이 변형이 바뀌며, 정지 사진인데도 밀려 들어오는 것처럼 보인다.
    """
    count = max(1, min(count, MAX_VARIANTS))
    palettes = common.WEIRD_PALETTES

    if photo_path is not None:
        palette = common.pick_palette(str(item["id"]), palettes)
        bases = [common.make_photo_background(photo_path, *palette)] * count
    else:
        # 팔레트를 crc32로 매번 뽑으면 이웃한 두 컷이 같은 색으로 걸릴 수 있고,
        # 그러면 컷이 바뀐 것으로 보이지 않는다. 순번으로 돌려 이웃은 항상 다르게 한다.
        start = common.pick_palette_index(str(item["id"]), palettes)
        bases = [common.make_background(*palettes[(start + i) % len(palettes)])
                 for i in range(count)]

    # 확대는 사진이든 그라데이션이든 똑같이 준다. 팔레트가 한 바퀴 돌아
    # 같은 색으로 돌아와도 화면은 계속 밀려 들어온다.
    variants = []
    for i, base in enumerate(bases):
        if i == 0:
            variants.append(base)
            continue
        zoom = 1.0 + ZOOM_STEP * i
        w, h = int(common.WIDTH / zoom), int(common.HEIGHT / zoom)
        left, top = (common.WIDTH - w) // 2, (common.HEIGHT - h) // 2
        cropped = base.crop((left, top, left + w, top + h))
        variants.append(cropped.resize((common.WIDTH, common.HEIGHT), Image.LANCZOS))
    return variants


def make_slide(background: Image.Image, role: str, text: str) -> Image.Image:
    """배경 한 장 위에 자막과 채널 표기를 얹는다."""
    img = background.copy()
    draw = ImageDraw.Draw(img)
    font_path = common.find_korean_font()

    if role == "hook":
        font = ImageFont.truetype(font_path, 78)
        fill, wrap, y = (255, 255, 255), 13, 620
    elif role in ("twist", "cta"):
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
    """구간별 TTS를 만들어 하나로 잇고, (오디오 경로, 구간별 길이)를 돌려준다.

    구간 길이는 오디오의 실제 길이와 정확히 같아야 한다. 짧은 문장에 하한을
    적용할 때 정적까지 함께 늘리는 이유다 — 영상만 늘리면 -shortest가
    마지막을 잘라낸다.
    """
    seg_paths, seg_durations = [], []

    for i, (_role, text) in enumerate(segments):
        seg_path = OUTPUT_DIR / f"seg_{item['id']}_{i}.mp3"
        common.tts_save_segment("ko", text, seg_path, use_elevenlabs_for_en=False)

        spoken = common.probe_duration(seg_path)
        if spoken <= 0:
            print(f"  [경고] {i}번 구간 길이를 재지 못해 기본값을 씁니다.", file=sys.stderr)

        gap = max(SEGMENT_GAP_SEC, MIN_SEGMENT_SEC - spoken)
        gap_path = OUTPUT_DIR / f"gap_{item['id']}_{i}.mp3"
        common.generate_silence(gap, gap_path)

        seg_paths += [seg_path, gap_path]
        seg_durations.append(spoken + gap)

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


def build_video(item, slide_paths, cuts, audio_path, out_path: Path) -> Path:
    concat_list = OUTPUT_DIR / f"concat_{item['id']}.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for path, cut in zip(slide_paths, cuts):
            f.write(f"file '{path}'\n")
            f.write(f"duration {cut.duration:.3f}\n")
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

{cta.pick(item)}

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
    if item is None:
        total = len(load_content())
        print(
            f"[중단] 준비된 {total}편을 모두 사용했습니다. 같은 영상을 다시 올리지 않도록\n"
            "       업로드하지 않고 종료합니다. weird_content.json에 새 시나리오를 추가하세요.",
            file=sys.stderr,
        )
        print(json.dumps({"skipped": True, "reason": "content_exhausted"}, ensure_ascii=False))
        return 0

    segments = narration_segments(item)
    print(f"[생성] #{item['id']} {item['title']}  ({audio_mode}, {len(segments)}구간)", file=sys.stderr)

    audio_path, durations = build_audio(item, segments, audio_mode)

    # 여기서 영상의 뼈대가 정해진다. 앞 HOOK_SEC초는 문장 경계를 무시하고
    # HOOK_CUT초마다 끊고, 그 뒤는 문장 경계를 지킨다.
    cuts = build_timeline(durations, hook_sec=HOOK_SEC, hook_cut=HOOK_CUT,
                          min_segment_sec=MIN_SEGMENT_SEC)

    # 배경 사진은 영상당 한 장만 받아 모든 컷이 공유한다.
    # 호출을 1회로 묶어 Pexels 무료 한도(시간당 200회)에 여유를 둔다.
    photo_path = None
    query = item.get("image_query", "")
    if query:
        candidate = OUTPUT_DIR / f"bg_{item['id']}.jpg"
        photo_path = common.fetch_background_photo(query, candidate)

    backgrounds = build_backgrounds(item, len(cuts), photo_path)

    slide_paths = []
    for i, cut in enumerate(cuts):
        role, text = segments[cut.segment_index]
        slide_path = OUTPUT_DIR / f"slide_{item['id']}_{i:03d}.png"
        make_slide(backgrounds[cut.variant % len(backgrounds)], role, text).save(slide_path)
        slide_paths.append(slide_path)

    video_path = OUTPUT_DIR / f"{prefix}_{item['id']}.mp4"
    build_video(item, slide_paths, cuts, audio_path, video_path)
    if photo_path is not None:
        photo_path.unlink(missing_ok=True)

    metadata_path = OUTPUT_DIR / f"metadata_{item['id']}.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(make_metadata(item), f, ensure_ascii=False, indent=2)

    log_usage(item, video_path)

    hook_cuts = sum(1 for c in cuts if c.duration <= HOOK_CUT + 1e-6)
    print(f"[완료] {video_path}  ({total_duration(cuts):.1f}초, "
          f"컷 {len(cuts)}개 / 앞 {HOOK_SEC:g}초에 {hook_cuts}개)", file=sys.stderr)
    print(json.dumps({
        "skipped": False,
        "video_path": str(video_path),
        "metadata_path": str(metadata_path),
        "content_id": item["id"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
