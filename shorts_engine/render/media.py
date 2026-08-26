"""기존 파이프라인(channel_food/scripts/common.py)의 검증된 함수를 끌어다 쓰는 어댑터.

600줄을 복제하지 않고 재사용한다. 가져오는 것:
  - edge-tts 한국어 합성          tts_save_segment
  - ffprobe 길이 측정             probe_duration
  - Pexels 배경 + 가독성 보정      fetch_background_photo / make_photo_background
  - 배경음 합성/믹싱               mix_ambience / mix_narration_with_ambience
  - mp3 안전 접합                  concat_audio
  - 폰트/팔레트/자막 그리기         find_korean_font / pick_palette / draw_centered

common.py를 shorts_engine 안으로 옮기지 않는 이유: 기존 파이프라인이 아직
그 파일로 매일 발행 중이다. 전환이 끝난 뒤에 옮기는 게 안전하다.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LEGACY = _REPO_ROOT / "channel_food" / "scripts"

if not _LEGACY.exists():  # pragma: no cover - 배치 오류 진단용
    raise ImportError(
        f"기존 common.py를 찾지 못했습니다: {_LEGACY}\n"
        "shorts_engine은 저장소 루트 아래에 있어야 합니다."
    )

if str(_LEGACY) not in sys.path:
    sys.path.insert(0, str(_LEGACY))

import common  # noqa: E402

# 재노출 — 호출부가 common을 직접 알 필요가 없게 한다.
WIDTH = common.WIDTH
HEIGHT = common.HEIGHT
WEIRD_PALETTES = common.WEIRD_PALETTES

tts_save_segment = common.tts_save_segment
probe_duration = common.probe_duration
generate_silence = common.generate_silence
concat_audio = common.concat_audio
fetch_background_photo = common.fetch_background_photo
make_photo_background = common.make_photo_background
make_background = common.make_background
mix_ambience = common.mix_ambience
mix_narration_with_ambience = common.mix_narration_with_ambience
find_korean_font = common.find_korean_font
pick_palette = common.pick_palette
draw_centered = common.draw_centered

__all__ = [
    "WIDTH",
    "HEIGHT",
    "WEIRD_PALETTES",
    "tts_save_segment",
    "probe_duration",
    "generate_silence",
    "concat_audio",
    "fetch_background_photo",
    "make_photo_background",
    "make_background",
    "mix_ambience",
    "mix_narration_with_ambience",
    "find_korean_font",
    "pick_palette",
    "draw_centered",
]
