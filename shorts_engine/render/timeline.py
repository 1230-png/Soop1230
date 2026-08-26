"""컷 타임라인 계산 — 실제 구현은 channel_food/scripts/timeline.py 에 있다.

같은 계산을 두 벌 두면 언젠가 갈라진다. 매일 발행 중인 파이프라인과
이 엔진이 같은 컷을 만들어야 하므로, 구현은 한 곳에만 두고 여기서는 재노출만 한다.
(render/media.py가 common.py를 끌어다 쓰는 것과 같은 이유, 같은 방식이다.)
"""

from __future__ import annotations

from render.media import _LEGACY  # noqa: F401  경로를 sys.path에 넣기 위한 임포트

from timeline import Cut, build_timeline, total_duration, variant_count  # noqa: E402

__all__ = ["Cut", "build_timeline", "total_duration", "variant_count"]
