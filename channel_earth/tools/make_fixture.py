"""렌더 확인용 **가짜** 지진 데이터를 만든다.

    python3 channel_earth/tools/make_fixture.py

왜 필요한가: 이 저장소를 만든 컨테이너에서 USGS 에 닿지 못했다(egress 403).
실제 응답 없이 화면과 소리를 확인하려면 형식이 같은 데이터가 있어야 한다.

**이 파일이 만든 것으로 영상을 내보내면 안 된다.** 숫자가 전부 지어낸
것이고, 지진 정보를 사실처럼 내보내는 것은 그 자체로 해가 된다. build.py 는
픽스처로 만든 빌드에 `synthetic: true` 를 박고, upload.py 가 그것을 보고
멈춘다.

그래도 **닮게** 만든다. 닮지 않으면 확인이 되지 않는다:

- 위치는 실제 지진대(환태평양·중앙해령·알프스히말라야) 주변에 뿌린다
- 규모는 구텐베르크-리히터를 따른다 — 규모가 1 오르면 건수는 약 1/10
- USGS 요약 피드는 미국 지역망의 작은 지진이 크게 섞인다. 관측망이 촘촘한
  곳이 지진이 많은 곳처럼 보이는 편향인데, 지도에서 실제로 그렇게 보이므로
  픽스처도 그 편향을 재현한다
"""

import argparse
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 실제 지진대의 대략적인 경로. (경도, 위도) 를 이어 만든 꺾은선이고, 이 선
# 주변에 지진을 뿌린다. 정밀한 판 경계가 아니라 모양만 맞춘 것이다.
BELTS = {
    "환태평양 동쪽": [(-72, -45), (-72, -30), (-76, -14), (-79, -5), (-84, 8),
                (-92, 15), (-98, 17), (-115, 30), (-125, 42), (-135, 55),
                (-150, 58), (-165, 54)],
    "환태평양 서쪽": [(175, 52), (160, 50), (148, 44), (142, 39), (140, 35),
                (132, 31), (128, 26), (122, 24), (124, 14), (126, 7),
                (128, 0), (120, -5), (110, -8), (100, -3), (95, 4)],
    "남서태평양": [(145, -6), (155, -8), (165, -12), (172, -16), (177, -25),
              (178, -37), (170, -45)],
    "중앙해령": [(-30, 62), (-33, 45), (-38, 30), (-42, 15), (-30, 0),
             (-15, -10), (-13, -25), (-15, -40), (-20, -55)],
    "알프스히말라야": [(14, 40), (25, 38), (35, 37), (45, 38), (55, 32),
                 (62, 30), (72, 34), (82, 29), (92, 26), (97, 22)],
}

# 관측망이 촘촘해 작은 지진까지 잡히는 곳. (경도, 위도, 퍼짐)
DENSE_NETWORKS = [
    (-119.5, 36.5, 3.0, "California"),
    (-151.0, 61.0, 4.0, "Alaska"),
    (-97.5, 36.0, 1.5, "Oklahoma"),
    (-66.5, 18.0, 1.2, "Puerto Rico"),
    (-155.4, 19.4, 0.8, "Hawaii"),
    (-112.0, 39.5, 2.0, "Utah"),
    (-118.5, 38.5, 2.0, "Nevada"),
]

# 구텐베르크-리히터의 b 값. 1.0 이면 규모가 1 오를 때 건수가 1/10 이 된다.
B_VALUE = 1.0


def belt_point(rng: random.Random) -> tuple[float, float]:
    """지진대 꺾은선 위의 한 점에 흔들림을 얹는다."""
    name = rng.choice(list(BELTS))
    path = BELTS[name]
    index = rng.randrange(len(path) - 1)
    (lon0, lat0), (lon1, lat1) = path[index], path[index + 1]
    t = rng.random()
    lon = lon0 + (lon1 - lon0) * t + rng.gauss(0, 2.2)
    lat = lat0 + (lat1 - lat0) * t + rng.gauss(0, 1.8)
    return _wrap(lon), max(-85.0, min(85.0, lat))


def network_point(rng: random.Random) -> tuple[float, float]:
    lon, lat, spread, _ = rng.choice(DENSE_NETWORKS)
    return _wrap(lon + rng.gauss(0, spread)), max(-85.0, min(85.0, lat + rng.gauss(0, spread * 0.7)))


def _wrap(lon: float) -> float:
    """경도를 -180..180 으로. 날짜변경선 근처에서 191.3 같은 값이 나온다."""
    return (lon + 180.0) % 360.0 - 180.0


def magnitude(rng: random.Random, floor: float, ceiling: float) -> float:
    """구텐베르크-리히터를 잘라서 뽑는다.

    누적 분포 N(>=M) ∝ 10^(-bM) 를 역변환한다. 그냥 균등 분포로 뽑으면
    규모 6이 규모 2만큼 흔해져서 화면이 거짓말을 한다.
    """
    u = rng.random()
    span = 1.0 - 10.0 ** (-B_VALUE * (ceiling - floor))
    return round(floor - math.log10(1.0 - u * span) / B_VALUE, 1)


def depth(rng: random.Random, mag: float) -> float:
    """대부분 얕고, 가끔 섭입대 깊은 지진."""
    if rng.random() < 0.12:
        return round(rng.uniform(70, 600), 1)
    return round(abs(rng.gauss(0, 18)) + 1.0, 1)


def build(count: int, seed: int, day_start_ms: int) -> dict:
    rng = random.Random(seed)
    features = []

    # 두 모집단을 따로 뽑는다. 하나의 분포에서 다 뽑으면 실제와 안 맞는다 —
    # 미국 지역망의 작은 지진은 그곳 관측망이 촘촘해서 과하게 많이 잡히는
    # 것이지, 전 지구 규모 분포의 일부가 아니다.
    #
    # 전 지구 기준으로 하루에 M4 이상은 서른몇 건, M5 이상은 서너 건,
    # M6 이상은 이삼 일에 한 건꼴이다. 그 수가 나오도록 전역 건수를 고정한다.
    global_count = min(count, max(0, int(round(rng.gauss(38, 6)))))
    for index in range(count):
        if index < global_count:
            lon, lat = belt_point(rng)
            mag = magnitude(rng, 4.0, 7.6)
        else:
            lon, lat = network_point(rng)
            mag = magnitude(rng, 0.5, 4.0)

        epoch = day_start_ms + rng.randrange(0, 24 * 3600 * 1000)
        features.append({
            "type": "Feature",
            "properties": {
                "mag": mag,
                "place": f"{rng.randint(1, 240)}km 지점 (가짜 데이터)",
                "time": epoch,
                "updated": epoch + 60_000,
                "tz": None,
                "status": "automatic",
                "tsunami": 0,
                "sig": int(mag * mag * 20),
                "magType": "mb" if mag >= 4 else "ml",
                "type": "earthquake",
                "title": f"M {mag:.1f} - 가짜 데이터",
            },
            "geometry": {"type": "Point",
                         "coordinates": [round(lon, 4), round(lat, 4),
                                         depth(rng, mag)]},
            "id": f"synthetic{index:05d}",
        })

        # 실제 피드에는 규모가 아직 안 정해진 줄이 섞여 온다. 파서가 그것을
        # 버리는지 확인하려면 픽스처에도 있어야 한다.
        if rng.random() < 0.02:
            broken = json.loads(json.dumps(features[-1]))
            broken["properties"]["mag"] = None
            broken["id"] = f"synthetic{index:05d}x"
            features.append(broken)

    features.sort(key=lambda f: f["properties"]["time"])
    return {
        "type": "FeatureCollection",
        "metadata": {
            "generated": day_start_ms + 24 * 3600 * 1000,
            "url": "SYNTHETIC — 실제 USGS 응답이 아니다",
            "title": "가짜 데이터 (렌더 확인용)",
            "status": 200,
            "api": "synthetic",
            "count": len(features),
        },
        "features": features,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="렌더 확인용 가짜 지진 데이터")
    parser.add_argument("--count", type=int, default=290)
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "data" / "fixtures" / "usgs_day_synthetic.json")
    args = parser.parse_args()

    # 2026-09-21 00:00 UTC. 고정해야 같은 씨앗에서 같은 파일이 나온다.
    payload = build(args.count, args.seed, 1_789_948_800_000)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print(f"{args.out} — {len(payload['features'])}건 (전부 가짜)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
