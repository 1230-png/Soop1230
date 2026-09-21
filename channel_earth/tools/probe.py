"""USGS 응답이 우리가 생각한 형식으로 오는지 확인한다. **표준 라이브러리만 쓴다.**

    python3 channel_earth/tools/probe.py

`pip install` 도 `ffmpeg` 도 필요 없다. 파이썬만 있으면 된다.

왜 이 파일이 따로 있는가: 이 코드를 만든 환경에서 USGS 에 닿지 못했고
(egress 403), 그래서 `lib/sources.py` 의 파서는 **문서로 공개된 스키마를
보고 쓴 것이지 실제 응답을 보고 쓴 것이 아니다.** 형식이 다르면 지금 있는
코드가 전부 헛것이므로, 그 한 가지를 가장 싸게 확인할 방법이 필요했다.

build.py 로도 확인은 되지만 numpy·Pillow·ffmpeg 를 다 깔아야 한다. 확인하려는
것은 응답 형식 하나인데 그 앞에 설치가 셋 놓이면, 설치에서 막힌 것인지
형식이 다른 것인지 구분이 안 된다.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import sources  # noqa: E402

EXPECTED_PROPS = {"mag", "place", "time", "depth 는 geometry 에 있다"}


def report(payload: dict) -> int:
    print("=" * 62)
    print("받은 응답의 생김새")
    print("=" * 62)
    print(f"최상위 칸: {', '.join(sorted(payload))}")

    meta = payload.get("metadata") or {}
    if meta:
        print(f"metadata.count: {meta.get('count')}")
        print(f"metadata.title: {meta.get('title')}")
        print(f"metadata.status: {meta.get('status')}")

    features = payload.get("features")
    if not isinstance(features, list):
        print("\n** features 배열이 없다. 스키마가 우리가 아는 것과 다르다. **")
        return 2
    print(f"features 개수: {len(features)}")

    if features:
        first = features[0]
        props = first.get("properties") or {}
        geom = first.get("geometry") or {}
        print(f"\nfeatures[0].properties 칸 ({len(props)}개):")
        print("  " + ", ".join(sorted(props)))
        print(f"\nfeatures[0].geometry: type={geom.get('type')!r} "
              f"coordinates={geom.get('coordinates')}")
        print("  (coordinates 는 [경도, 위도, 깊이km] 순서여야 한다)")

        print("\n우리가 쓰는 칸이 있는가:")
        for name in ("mag", "place", "time"):
            mark = "있음" if name in props else "** 없음 **"
            print(f"  properties.{name:<6} {mark}")
        coords = geom.get("coordinates")
        ok = isinstance(coords, list) and len(coords) >= 3
        print(f"  geometry.coordinates  {'있음 (3개)' if ok else '** 이상함 **'}")

    print("\n" + "=" * 62)
    print("파서에 넣어 보기")
    print("=" * 62)
    try:
        quakes = sources.parse_quakes(payload)
    except ValueError as error:
        print(f"** 파싱 실패: {error} **")
        return 2

    if not quakes:
        print("** 한 건도 읽지 못했다 **")
        return 2

    mags = [q.mag for q in quakes]
    print(f"읽은 건수: {len(quakes)} / {len(features)}")
    print(f"규모 범위: {min(mags):.1f} ~ {max(mags):.1f}")
    print(f"M4.0 이상: {sum(1 for m in mags if m >= 4)}건  "
          f"M5.0 이상: {sum(1 for m in mags if m >= 5)}건")
    print(f"깊이 범위: {min(q.depth_km for q in quakes):.1f} ~ "
          f"{max(q.depth_km for q in quakes):.1f} km")
    print(f"기간: {quakes[0].time:%Y-%m-%d %H:%M} ~ {quakes[-1].time:%m-%d %H:%M} UTC")

    print("\n가장 컸던 셋:")
    for quake in sorted(quakes, key=lambda q: -q.mag)[:3]:
        print(f"  M {quake.mag:.1f}  {quake.place[:44]}  "
              f"(깊이 {quake.depth_km:.0f}km)")

    # 눈으로 확인할 마지막 한 가지. 건수가 터무니없으면 형식은 맞아도
    # 엉뚱한 피드를 받은 것이다.
    if len(quakes) < 20:
        print(f"\n** 건수가 {len(quakes)}건뿐이다. 하루치라면 보통 200~400건이다. "
              "기간을 잘못 골랐거나 피드가 이상하다. **")
        return 1

    print("\n형식이 우리가 아는 것과 맞다. 다음 단계로 가도 된다.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="USGS 응답 형식 확인 (표준 라이브러리만)")
    parser.add_argument("--window", default="day",
                        choices=sorted(sources.FEEDS))
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).resolve().parent.parent
                        / "build" / "usgs_response.json",
                        help="받은 응답을 그대로 적어 둘 곳")
    args = parser.parse_args()

    url = sources.FEEDS[args.window]
    print(f"받는 중: {url}\n")
    try:
        payload = sources.fetch_json(url)
    except RuntimeError as error:
        print(f"** 받지 못했다: {error} **")
        print("\n인터넷이 막혀 있거나 USGS 가 점검 중이다. "
              "브라우저로 위 주소가 열리는지 먼저 볼 것.")
        return 3

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"응답을 적어 뒀다: {args.out}\n")

    code = report(payload)
    if code:
        print(f"\n이 파일을 그대로 보내 줄 것: {args.out}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
