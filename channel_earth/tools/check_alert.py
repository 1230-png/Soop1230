#!/usr/bin/env python3
"""큰 지진이 방금 났는지 확인하고, 냈다면 무엇을 낼지 알려 준다.

30분마다 도는 워크플로가 이것을 먼저 부른다. 낼 것이 없으면 거기서 끝나므로
**대부분의 실행은 몇 초 만에 끝나고 러너 시간을 쓰지 않는다.** 렌더링은 낼
것이 있을 때만 시작한다.

왜 발행 기록을 여기서 남기지 않는가: 업로드가 실패했는데 "냈다"고 적으면 그
지진은 두 번 다시 나가지 않는다. 기록은 업로드가 성공한 뒤 `--record` 로
따로 남긴다.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import alert, sources, titles   # noqa: E402

STATE = Path(__file__).resolve().parent.parent / "data" / "published_alerts.json"


def emit(name: str, value: str) -> None:
    """GitHub Actions 출력. 로컬에서 돌리면 화면에만 찍힌다."""
    print(f"{name}={value}")
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--window", default="day", choices=sorted(sources.FEEDS),
                    help="어느 피드를 볼지. day 가 기본 — hour 는 경계에서 "
                         "방금 난 지진을 놓칠 수 있다")
    ap.add_argument("--cache", type=Path, help="이 파일이 있으면 네트워크를 타지 않는다")
    ap.add_argument("--state", type=Path, default=STATE)
    ap.add_argument("--now", help="ISO 시각. 시험용이고 비우면 현재 UTC")
    ap.add_argument("--record", help="업로드에 성공한 지진 id. 이것만 기록하고 끝난다")
    ap.add_argument("--video-id", default="")
    ap.add_argument("--meta", type=Path,
                    help="metadata.json. --record 와 함께 주면 규모·제목도 "
                         "기록에 남는다 (없어도 기록은 된다)")
    args = ap.parse_args(argv)

    now = (dt.datetime.fromisoformat(args.now) if args.now
           else dt.datetime.now(dt.timezone.utc))
    state = alert.load_state(args.state)

    # **기록은 네트워크를 타지 않는다.** 업로드가 성공한 뒤에 도는 단계인데
    # 여기서 피드를 다시 받다가 실패하면, 이미 올라간 영상을 기록하지 못해
    # 30분 뒤 같은 지진이 또 나간다. 중복을 막는 데 필요한 것은 id 뿐이다.
    if args.record:
        extra = {}
        if args.meta and args.meta.exists():
            try:
                meta = json.loads(args.meta.read_text(encoding="utf-8"))
                extra = {"mag": meta.get("max_magnitude"),
                         "place": meta.get("title", "")}
            except (OSError, ValueError):
                # 기록 자체를 막을 이유는 아니다 — id 만 있으면 중복은 막힌다.
                print("[alert] metadata.json 을 읽지 못했다 — id 만 적는다",
                      file=sys.stderr)
        alert.save_state(args.state, alert.record_id(
            state, args.record, now, video_id=args.video_id, **extra))
        print(f"[alert] 기록: {args.record} (video {args.video_id or '없음'})",
              file=sys.stderr)
        return 0

    quakes = sources.load_quakes(args.window, cache=args.cache)

    quake, reason = alert.pick_event(quakes, state, now)
    print(f"[alert] {reason}", file=sys.stderr)

    if quake is None:
        emit("publish", "false")
        return 0

    emit("publish", "true")
    emit("quake_id", quake.id)
    emit("magnitude", f"{quake.mag:.1f}")
    emit("title", titles.alert_title(quake, len(quakes)))
    print(json.dumps({
        "id": quake.id, "mag": quake.mag, "place": quake.place,
        "region_ko": titles.region_ko(quake.place),
        "time": quake.time.isoformat(),
    }, ensure_ascii=False, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
