"""머니로직 영상 렌더링 (moviepy).

기존 render.py를 대체한다. 바뀐 점:

  - 단색 RGB(15,23,42) 배경 -> 그라데이션·격자 배경이 아주 느리게 패닝
  - 타이틀 카드 / 아웃트로 카드 추가
  - 자막 하드번 (timeline에 text가 있을 때)
  - 채널 워터마크 + 하단 진행바
  - [KEY:] 차트 오버레이가 6초 상한에 잘리지 않고 발화 길이만큼 유지

## moviepy 사용 시 지키는 규칙 (이미 겪은 버그 재발 방지)

  - .resize()를 호출하지 않는다. moviepy 1.0.3의 resize는 최신 Pillow에서
    삭제된 Image.ANTIALIAS를 참조해 터진다. 배경 움직임은 확대가 아니라
    '크게 만들어 놓고 이동(set_position)'으로 구현했다.
  - TextClip을 쓰지 않는다. ImageMagick 외부 설치 의존이라 Windows에서
    잘 깨진다. 글자는 전부 visuals.py가 Pillow로 그린다.
  - 차트 PNG도 리사이즈하지 않는다. chart.py가 이미 목표 크기로 만든다.
"""

import math
from pathlib import Path

import numpy as np
from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoClip,
)
from PIL import Image

import visuals

WIDTH, HEIGHT = visuals.WIDTH, visuals.HEIGHT
FPS = 30

# 타이틀 카드를 먼저 보여주고 그 뒤에 나레이션을 시작한다.
# 타이틀을 0초부터 나레이션과 겹쳐 틀면 첫 자막이 타이틀 글자 바로 밑에
# 붙어서 두 덩어리가 싸운다(실제로 첫 렌더링에서 그렇게 나왔다).
# 오디오와 timeline을 통째로 INTRO_SEC만큼 밀어서 아예 구간을 분리한다.
INTRO_SEC = 3.5       # 타이틀만 나오는 도입부
OUTRO_SEC = 3.5       # 아웃트로 카드 노출 시간
FADE = 0.5            # 카드 페이드 인/아웃

# [KEY:] 차트 오버레이 노출 시간.
#   기존에는 MAX_OVERLAY_SEC=6 고정이라, 해당 구간 발화가 6초보다 길면
#   문장이 안 끝났는데 차트가 먼저 사라졌다(미완료 항목 #2).
#   이제 기본값은 '그 구간 발화가 끝날 때까지'다. 상한을 다시 두고 싶으면
#   MAX_OVERLAY_SEC에 초를 넣으면 된다.
MAX_OVERLAY_SEC = None
MIN_OVERLAY_SEC = 2.0  # 너무 짧으면 깜빡이는 것처럼 보여서 최소 시간은 준다

PAN_PERIOD = 46.0      # 배경이 한 번 왕복하는 데 걸리는 초. 길수록 잔잔하다.

CHANNEL_NAME = "머니로직"


def _pil_to_clip(img: Image.Image) -> ImageClip:
    """PIL RGBA 이미지를 투명도가 살아있는 ImageClip으로 바꾼다.

    moviepy는 알파 채널을 알아서 읽지 않는다. RGB 본체와 마스크를 따로
    만들어 붙여야 배경이 비친다.
    """
    arr = np.array(img.convert("RGBA"))
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3].astype(float) / 255.0
    return ImageClip(rgb).set_mask(ImageClip(alpha, ismask=True))


def _background_clip(duration: float) -> ImageClip:
    """프레임보다 큰 배경을 만들어 천천히 움직인다.

    확대(zoom)가 아니라 이동(pan)이라서 resize를 타지 않는다. 이미지가
    프레임보다 크므로 어느 위치에서도 빈 공간이 생기지 않는다.
    """
    bg = visuals.make_background()
    bw, bh = bg.size

    # 위치 범위: 오른쪽/아래로 넘치는 만큼만 왼쪽/위로 움직일 수 있다.
    span_x = WIDTH - bw   # 음수
    span_y = HEIGHT - bh  # 음수

    def position(t):
        # 서로 다른 주기의 사인파를 써서 왕복이 눈에 띄지 않게 한다.
        fx = 0.5 + 0.5 * math.sin(2 * math.pi * t / PAN_PERIOD)
        fy = 0.5 + 0.5 * math.sin(2 * math.pi * t / (PAN_PERIOD * 1.37) + 1.1)
        return (span_x * fx, span_y * fy)

    return ImageClip(np.array(bg)).set_duration(duration).set_position(position)


def _progress_bar_clip(duration: float) -> VideoClip:
    """하단 진행바. 폭이 매 프레임 달라지므로 그때그때 그린다."""
    def make_frame(t):
        return np.array(visuals.make_progress_bar_row(t / duration))

    return (
        VideoClip(make_frame, duration=duration)
        .set_position((0, HEIGHT - 8))
    )


def _overlay_duration(segment_duration: float) -> float:
    """차트를 몇 초 띄울지. MAX_OVERLAY_SEC이 None이면 발화 끝까지."""
    shown = max(segment_duration, MIN_OVERLAY_SEC)
    if MAX_OVERLAY_SEC is not None:
        shown = min(shown, MAX_OVERLAY_SEC)
    return shown


def _chart_clip(chart_path: Path, start: float, duration: float) -> ImageClip:
    """차트 PNG를 화면 가운데에 얹는다. 크기는 손대지 않는다."""
    chart = Image.open(chart_path)
    x = (WIDTH - chart.width) / 2
    y = (HEIGHT - chart.height) / 2 - 40  # 자막과 겹치지 않게 살짝 위로

    return (
        _pil_to_clip(chart)
        .set_start(start)
        .set_duration(duration)
        .set_position((x, y))
        .crossfadein(0.4)
        .crossfadeout(0.4)
    )


def build_video(audio_path, out_path, ticker: str, topic: str, date_str: str,
                timeline=None, chart_path=None,
                channel_name: str = CHANNEL_NAME) -> Path:
    """오디오 + 시각 요소를 합쳐 최종 mp4를 만든다.

    audio_path : tts가 만든 전체 나레이션 오디오
    timeline   : [{"keyword": str, "start": float, "duration": float,
                   "text": str(선택)}, ...]
                 text가 있으면 그 구간 자막을 하드번한다. 없으면 자막 없이
                 나머지 요소만 렌더링한다(기존 tts.py와도 그대로 호환).
    chart_path : chart.py가 만든 차트 PNG. None이면 차트 오버레이 생략.
    """
    audio_path, out_path = Path(audio_path), Path(out_path)
    timeline = timeline or []

    audio = AudioFileClip(str(audio_path))
    # 도입부(타이틀) + 나레이션 + 아웃트로. 나레이션은 타이틀이 끝난 뒤
    # 시작하므로 자막이 타이틀과 겹치지 않는다.
    duration = INTRO_SEC + audio.duration + OUTRO_SEC
    # 그냥 AudioFileClip에 set_start만 하면 clip.audio로 붙였을 때 시작
    # 오프셋이 무시된다. CompositeAudioClip으로 감싸야 앞쪽 INTRO_SEC이
    # 실제 무음으로 들어가고 말과 자막 타이밍이 맞는다.
    audio = CompositeAudioClip([audio.set_start(INTRO_SEC)]).set_duration(duration)

    layers = [_background_clip(duration)]

    # 워터마크와 진행바는 영상 내내 유지 — 채널을 반복 노출하고,
    # 남은 길이를 보여줘서 이탈을 줄인다.
    layers.append(
        _pil_to_clip(visuals.make_watermark(channel_name)).set_duration(duration)
    )
    layers.append(_progress_bar_clip(duration))

    # 타이틀 카드
    layers.append(
        _pil_to_clip(visuals.make_title_card(ticker, topic, date_str))
        .set_start(0)
        .set_duration(INTRO_SEC)
        .crossfadein(FADE)
        .crossfadeout(FADE)
    )

    has_subtitle_text = any(seg.get("text") for seg in timeline)

    for seg in timeline:
        # timeline의 start는 '오디오 안에서의 시각'이다. 오디오 자체를
        # INTRO_SEC만큼 밀었으니 오버레이도 같이 밀어야 말과 화면이 맞는다.
        start = INTRO_SEC + float(seg["start"])
        seg_duration = float(seg["duration"])
        shown = _overlay_duration(seg_duration)

        if chart_path is not None:
            layers.append(_chart_clip(Path(chart_path), start, shown))

        keyword = seg.get("keyword")
        if keyword:
            layers.append(
                _pil_to_clip(visuals.make_keyword_label(keyword))
                .set_start(start)
                .set_duration(shown)
                .crossfadein(0.3)
                .crossfadeout(0.3)
            )

        text = seg.get("text")
        if text:
            # 자막은 차트와 달리 그 구간 발화 내내 떠 있어야 한다.
            layers.append(
                _pil_to_clip(visuals.make_subtitle(text))
                .set_start(start)
                .set_duration(seg_duration)
                .set_position((0, HEIGHT - 200))
            )

    # 아웃트로
    layers.append(
        _pil_to_clip(visuals.make_outro_card(channel_name))
        .set_start(duration - OUTRO_SEC)
        .set_duration(OUTRO_SEC)
        .crossfadein(FADE)
    )

    video = (
        CompositeVideoClip(layers, size=(WIDTH, HEIGHT))
        .set_duration(duration)
        .set_audio(audio)
    )

    # 클립 자체에도 fps를 박아둔다.
    # moviepy 1.0.3은 decorator<5.0을 요구하는데, 환경에 decorator 5.x가
    # 깔려 있으면 use_clip_fps_by_default 데코레이터가 write_videofile에
    # 넘긴 인자를 통째로 흘려버린다(fps는 물론 threads, preset까지).
    # 그러면 "must be real number, not NoneType"으로 터진다 — 실제로 겪음.
    # 근본 해결은 requirements.txt에 decorator<5.0을 고정하는 것이고,
    # 이 한 줄은 그 상황에서도 최소한 fps는 살아남게 하는 보험이다.
    video.fps = FPS

    out_path.parent.mkdir(parents=True, exist_ok=True)
    video.write_videofile(
        str(out_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="ultrafast",
        logger=None,
    )

    video.close()
    audio.close()

    if not has_subtitle_text and timeline:
        print(
            "[render] timeline에 text가 없어 자막을 넣지 않았습니다. "
            "tts.synthesize_with_timeline()이 각 구간의 원문을 "
            "text 필드에 담아 주면 자막이 자동으로 켜집니다."
        )

    return out_path
