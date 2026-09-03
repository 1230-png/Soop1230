"""대본 하나를 세로 쇼츠 영상으로 렌더링한다.

MoviePy 대신 ffmpeg를 직접 호출한다. MoviePy는 프레임을 파이썬으로 왕복시켜
같은 결과를 몇 배 느리게, 훨씬 많은 메모리로 만든다. 여기서 필요한 것은
정지 이미지 이어붙이기 + 오디오 먹싱뿐이라 ffmpeg의 concat demuxer로 충분하다.

파이프라인:
  문장별 TTS → 길이 측정 → build_timeline → 배경 변형 생성 → 슬라이드 렌더
  → concat(무음 영상) → 오디오 먹싱
재인코딩은 한 번만 일어난다.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from render import media
from render.timeline import Cut, build_timeline, total_duration

logger = logging.getLogger(__name__)

FPS = 30
# 훅 구간에서 배경이 조금씩 확대되며 정지 이미지에 움직임을 준다.
_ZOOM_STEP = 0.035
_MAX_VARIANTS = 12

# 문장 사이 짧은 정적. 문장이 붙어 들리는 것을 막는다.
SEGMENT_GAP_SEC = 0.3


@dataclass
class RenderRequest:
    """렌더링 입력. DB의 Script에서 그대로 만들 수 있다."""

    script_id: int
    title: str
    hook: str
    body: list[str]
    cta_question: str
    image_query: str
    ambience: list[str] | None = None

    def segments(self) -> list[str]:
        """화면과 나레이션의 단위. 훅 → 본문 → 댓글 유도 질문 순."""
        return [self.hook, *self.body, self.cta_question]


@dataclass
class RenderResult:
    video_path: Path
    duration_sec: float
    cut_count: int
    hook_cut_count: int
    used_photo: bool


def _run(cmd: list[str]) -> None:
    """ffmpeg 호출. 실패 시 stderr를 그대로 올려 원인을 잃지 않는다."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-8:])
        raise RuntimeError(f"ffmpeg 실패 ({' '.join(cmd[:6])}...):\n{tail}")


def _synthesize(req: RenderRequest, work: Path) -> tuple[Path, list[float]]:
    """문장별로 음성을 만들고, 각 길이를 재서 하나로 잇는다."""
    parts: list[Path] = []
    durations: list[float] = []

    for i, sentence in enumerate(req.segments()):
        seg = work / f"seg_{i}.mp3"
        media.tts_save_segment("ko", sentence, seg, use_elevenlabs_for_en=False)

        gap = work / f"gap_{i}.mp3"
        media.generate_silence(SEGMENT_GAP_SEC, gap)

        spoken = media.probe_duration(seg)
        if spoken <= 0:
            # ffprobe 실패. build_timeline이 하한으로 보정하므로 여기서는 기록만 한다.
            logger.warning("구간 %d의 길이를 재지 못했습니다", i)
        durations.append(spoken + SEGMENT_GAP_SEC)
        parts += [seg, gap]

    narration = work / "narration.mp3"
    # 바이트 접합이 아니라 concat demuxer로 재인코딩한다.
    # 원시 mp3를 이어붙이면 중간에 프레임 헤더가 남아 이후 필터에서 터진다.
    media.concat_audio(parts, narration)
    for p in parts:
        p.unlink(missing_ok=True)
    return narration, durations


def _prepare_backgrounds(
    req: RenderRequest, work: Path, count: int
) -> tuple[list[Image.Image], bool]:
    """배경 변형을 만든다.

    사진은 영상당 한 장만 받고 크롭만 다르게 한다. 훅 구간에서 0.5초마다
    화면이 바뀔 때 조금씩 확대되어 움직이는 것처럼 보인다.
    Pexels 키가 없거나 실패하면 그라데이션으로 되돌아간다.
    """
    count = min(count, _MAX_VARIANTS)
    photo = None
    if req.image_query:
        photo = media.fetch_background_photo(req.image_query, work / "bg.jpg")

    if photo is None:
        # 사진이 없으면 팔레트만 바꾼 그라데이션. 생성 비용이 낮아 매번 만들어도 된다.
        return [
            media.make_background(
                *media.pick_palette(f"{req.script_id}-{i}", media.WEIRD_PALETTES)
            )
            for i in range(count)
        ], False

    # make_photo_background는 블러 + 리사이즈 + 합성이라 비싸다.
    # 변형마다 부르면 같은 작업을 12번 반복하게 되므로 한 번만 만들고 크롭만 달리한다.
    palette = media.pick_palette(str(req.script_id), media.WEIRD_PALETTES)
    base = media.make_photo_background(photo, *palette)

    variants: list[Image.Image] = [base]
    for i in range(1, count):
        # 중앙을 기준으로 조금씩 확대해 컷마다 다른 화면을 만든다.
        zoom = 1.0 + _ZOOM_STEP * i
        w, h = int(media.WIDTH / zoom), int(media.HEIGHT / zoom)
        left, top = (media.WIDTH - w) // 2, (media.HEIGHT - h) // 2
        cropped = base.crop((left, top, left + w, top + h))
        variants.append(cropped.resize((media.WIDTH, media.HEIGHT), Image.LANCZOS))

    return variants, True


def _draw_slide(
    background: Image.Image, text: str, role: str, font_path: str
) -> Image.Image:
    """배경 위에 자막을 얹는다."""
    img = background.copy()
    draw = ImageDraw.Draw(img)

    if role == "hook":
        font, fill, wrap, y = ImageFont.truetype(font_path, 78), (255, 255, 255), 13, 620
    elif role == "cta":
        font, fill, wrap, y = ImageFont.truetype(font_path, 70), (232, 196, 120), 14, 660
    else:
        font, fill, wrap, y = ImageFont.truetype(font_path, 60), (226, 230, 238), 16, 700

    media.draw_centered(draw, text, font, y, fill=fill, wrap_width=wrap, line_gap=24)
    return img


def _role_of(index: int, last: int) -> str:
    if index == 0:
        return "hook"
    if index == last:
        return "cta"
    return "body"


def render(
    req: RenderRequest,
    out_path: Path,
    work_dir: Path,
    hook_sec: float = 3.0,
    hook_cut: float = 0.5,
) -> RenderResult:
    """대본 하나를 mp4로 만든다."""
    work_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    narration, durations = _synthesize(req, work_dir)
    cuts: list[Cut] = build_timeline(durations, hook_sec=hook_sec, hook_cut=hook_cut)

    variants, used_photo = _prepare_backgrounds(req, work_dir, len(cuts))
    font_path = media.find_korean_font()
    sentences = req.segments()
    last_index = len(sentences) - 1

    # 슬라이드를 컷 단위로 렌더한다. 훅 구간에서는 같은 문장이 배경만 바뀌며 반복된다.
    slide_paths: list[Path] = []
    for i, cut in enumerate(cuts):
        bg = variants[cut.variant % len(variants)]
        text = sentences[cut.segment_index]
        role = _role_of(cut.segment_index, last_index)
        path = work_dir / f"slide_{i:03d}.png"
        _draw_slide(bg, text, role, font_path).save(path)
        slide_paths.append(path)

    # concat demuxer는 마지막 항목의 duration을 무시한다. 한 번 더 적어야
    # 마지막 컷이 통째로 잘려나가지 않는다.
    concat_list = work_dir / "concat.txt"
    lines = []
    for path, cut in zip(slide_paths, cuts):
        lines.append(f"file '{path.resolve()}'")
        lines.append(f"duration {cut.duration:.3f}")
    lines.append(f"file '{slide_paths[-1].resolve()}'")
    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

    silent = work_dir / "silent.mp4"
    _run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-vf", f"scale={media.WIDTH}:{media.HEIGHT},fps={FPS}",
        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "23",
        str(silent),
    ])

    audio = narration
    if req.ambience:
        total = total_duration(cuts)
        amb = work_dir / "ambience.mp3"
        if media.mix_ambience(req.ambience, total, amb) is not None:
            mixed = work_dir / "audio.mp3"
            media.mix_narration_with_ambience(narration, amb, mixed)
            audio = mixed

    _run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(silent), "-i", str(audio),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0", "-shortest",
        str(out_path),
    ])

    hook_count = sum(1 for c in cuts if c.duration <= hook_cut + 1e-6)
    return RenderResult(
        video_path=out_path,
        duration_sec=total_duration(cuts),
        cut_count=len(cuts),
        hook_cut_count=hook_count,
        used_photo=used_photo,
    )
