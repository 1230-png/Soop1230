"""공공 API에서 데이터를 받아 온다. 지금은 USGS 지진 피드 하나.

**이 저장소를 만든 컨테이너에서는 이 API에 닿지 못했다.** 조직의 egress
정책이 `earthquake.usgs.gov` 로 나가는 CONNECT 를 403 으로 막는다. 그래서
아래 파싱 코드는 **USGS 가 문서로 공개한 스키마를 보고 쓴 것이지, 실제
응답을 보고 쓴 것이 아니다.** GitHub Actions 에는 그 제한이 없으므로 거기서는
돌지만, 첫 실행은 `--dump` 로 응답을 그대로 떨어뜨려 놓고 눈으로 확인할 것.

그래서 파서를 방어적으로 썼다. 모르는 칸이 있어도 죽지 않고, 필요한 칸이
없는 줄만 버린다. 스키마가 예상과 다르면 **몇 줄이 버려졌는지 찍는다** —
조용히 빈 영상이 나오는 것이 제일 나쁘다.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# USGS 가 미리 말아 둔 요약 피드. 키가 필요 없고 1분마다 갱신된다.
# 기간별로 파일이 따로 있어서, 필요한 것만 받으면 된다.
FEEDS = {
    "hour": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson",
    "day": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
    "week": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson",
    "month": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson",
}

USER_AGENT = "channel_earth/1.0 (+https://github.com/1230-png/Soop1230)"
TIMEOUT = 45
RETRIES = 4


@dataclass(frozen=True)
class Quake:
    """지진 한 건. 화면과 소리가 쓰는 값만 남긴다.

    USGS 응답에는 칸이 스물다섯 개쯤 되는데 대부분 쓰지 않는다. 여기서
    좁혀 두면 뒷단이 응답 형식에 묶이지 않는다 — 나중에 다른 기관 피드를
    더해도 이 타입만 맞추면 된다.
    """

    id: str
    time: dt.datetime      # UTC
    lat: float
    lon: float
    depth_km: float
    mag: float
    place: str

    @property
    def energy(self) -> float:
        """규모를 에너지에 비례하는 값으로.

        규모는 로그 눈금이라 4.0 과 6.0 을 막대 길이로 그리면 1.5배로
        보이지만 실제로 방출된 에너지는 1,000배다. 화면에서 점 크기나
        소리 크기를 정할 때 이 값을 쓰면 "느낌"이 실제에 가까워진다.
        """
        return 10.0 ** (1.5 * self.mag)


def fetch_json(url: str, *, retries: int = RETRIES, timeout: int = TIMEOUT) -> dict:
    """받아서 JSON 으로. 실패하면 물러났다 다시.

    USGS 는 무료이고 키가 없어 할당량 걱정은 없지만, 점검이나 일시적인
    503 은 있다. 하루 한 번 도는 작업이 그 한 번에 걸려 결번이 되지 않도록
    기다렸다 다시 한다.
    """
    last = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last = error
            if attempt == retries:
                break
            wait = 5 * (2 ** (attempt - 1))
            print(f"[source] {type(error).__name__} — {wait}초 뒤 다시 "
                  f"({attempt}/{retries - 1})", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"{url} 를 {retries}번 모두 받지 못했다: {last}")


def parse_quakes(payload: dict) -> list[Quake]:
    """GeoJSON 을 Quake 목록으로. 못 읽는 줄은 버리고 몇 개인지 찍는다.

    `mag` 이 null 인 줄이 실제로 온다 — 자동 검출 직후라 규모가 아직 안
    정해진 사건이다. 그런 줄을 0 으로 치면 화면에 점이 찍히고 통계가 틀어지므로
    버린다. **버린 개수를 찍는 것이 중요하다.** 스키마가 바뀌어 전부 버려지면
    지진이 한 건도 없는 날과 화면상 구분이 안 된다.
    """
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("GeoJSON 에 features 배열이 없다. 스키마가 바뀌었는가")

    quakes: list[Quake] = []
    dropped = 0
    for feature in features:
        try:
            props = feature["properties"]
            lon, lat, depth = (feature["geometry"]["coordinates"] + [0.0, 0.0, 0.0])[:3]
            mag = props["mag"]
            epoch_ms = props["time"]
            if mag is None or epoch_ms is None or lon is None or lat is None:
                dropped += 1
                continue
            quakes.append(Quake(
                id=str(feature.get("id") or props.get("code") or len(quakes)),
                time=dt.datetime.fromtimestamp(epoch_ms / 1000.0, dt.timezone.utc),
                lat=float(lat), lon=float(lon),
                # 깊이가 음수로 오는 줄이 있다(해수면 위 기준점). 0 으로 눌러 둔다.
                depth_km=max(0.0, float(depth if depth is not None else 0.0)),
                mag=float(mag),
                place=str(props.get("place") or "").strip(),
            ))
        except (KeyError, TypeError, ValueError, IndexError):
            dropped += 1

    if dropped:
        print(f"[source] {dropped}건은 필요한 값이 없어 제외 "
              f"(전체 {len(features)}건)", file=sys.stderr)
    if features and not quakes:
        raise ValueError(
            f"{len(features)}건을 받았는데 한 건도 읽지 못했다. "
            "응답 스키마가 바뀐 것으로 보인다 — --dump 로 응답을 확인할 것")

    quakes.sort(key=lambda q: q.time)
    return quakes


def load_quakes(window: str = "day", *, cache: Path | None = None,
                dump: Path | None = None) -> list[Quake]:
    """이 기간의 지진. `cache` 가 있으면 네트워크를 타지 않는다.

    캐시를 두는 이유는 비용이 아니라 **재현성**이다. 같은 날의 영상을 다시
    만들었을 때 화면이 달라지면 무엇을 고쳤는지 비교할 수가 없다. 피드는
    1분마다 갱신되므로 캐시 없이는 두 번 다시 같은 영상이 안 나온다.
    """
    if cache and cache.exists():
        payload = json.loads(cache.read_text(encoding="utf-8"))
        print(f"[source] 캐시 사용: {cache}", file=sys.stderr)
    else:
        if window not in FEEDS:
            raise ValueError(f"모르는 기간: {window!r} (가능: {', '.join(FEEDS)})")
        payload = fetch_json(FEEDS[window])
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(payload, ensure_ascii=False),
                             encoding="utf-8")

    if dump:
        dump.parent.mkdir(parents=True, exist_ok=True)
        dump.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        print(f"[source] 응답을 그대로 적었다: {dump}", file=sys.stderr)

    quakes = parse_quakes(payload)
    print(f"[source] 지진 {len(quakes)}건 "
          f"(규모 {min(q.mag for q in quakes):.1f}~"
          f"{max(q.mag for q in quakes):.1f})" if quakes else "[source] 0건",
          file=sys.stderr)
    return quakes
