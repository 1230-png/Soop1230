"""발행할 가치가 있는 지진이 방금 났는지 판단한다.

**왜 정해진 시각 발행만으로는 안 되는가.** 「지진」 검색량은 평소에 낮고, 큰
것이 하나 오면 몇 시간 치솟았다가 가라앉는다. 매일 08:00 KST 에 「어제 하루치
지도」를 내는 것은 수요가 없는 시각에 공급하는 것이다. 같은 저장소의 측정
기록이 그 결과를 보여 준다 — @귀트는일본어 는 정해진 시각에 롱폼을 꾸준히
냈고 8편 중 7편이 0회다(2026-09-27 스냅샷).

구독자가 없는 채널에서 조회수가 들어올 길은 셋뿐이고,

- 구독 피드 — 구독자가 없으면 없다
- 추천(suggested) — 시청 신호가 먼저 있어야 시작되므로 부트스트랩이 안 된다
- **검색 — 구독자 0명에서도 작동하는 유일한 경로**

검색만 남는다. 그리고 검색은 **수요가 있는 순간에만** 있다. 그 순간을 잡는
것이 이 파일이다.

같이 지키는 것: **틀을 반복 재생산하지 않는다.** 아무 지진에나 반응하면 하루에
수십 편이 나가고 그것이 정확히 유튜브가 거르는 모양이다(CLAUDE.md). 그래서
문턱을 높게 두고 냉각 시간을 둔다. M6.0 이상은 전 세계에서 한 해 100~150건
정도라 주 2~3편에 그친다.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

# 전 세계 문턱. 이 아래는 한국어권에서 기사도 검색도 거의 나지 않는다.
GLOBAL_MAG = 6.0

# 한국어 화자에게 가까운 곳은 문턱을 낮춘다. 일본 M5.0 은 한국 뉴스에 뜨고
# 검색도 뒤따르지만, 같은 규모가 남태평양에서 나면 아무 일도 일어나지 않는다.
# **검색 수요는 규모가 아니라 관심에서 나온다.**
NEAR_MAG = 5.0
NEAR_BOX = (24.0, 46.0, 122.0, 146.0)   # lat_min, lat_max, lon_min, lon_max

# 이보다 오래된 지진은 내지 않는다. 검색이 이미 지나갔고, 늦게 올린 영상은
# 그 검색어에서 이미 자리 잡은 뉴스 영상들 뒤에 붙는다.
FRESH_HOURS = 6.0

# 연달아 내지 않는다. 큰 지진은 여진을 수십 개 끌고 오는데 그것마다 한 편씩
# 내면 같은 틀의 반복 생산이 된다.
COOLDOWN_HOURS = 8.0

# 냉각 시간을 무시하는 규모. 이 급은 그 자체가 따로 다뤄야 하는 사건이다.
OVERRIDE_MAG = 7.0

STATE_VERSION = 1


def near_korea(lat: float, lon: float) -> bool:
    lat_min, lat_max, lon_min, lon_max = NEAR_BOX
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def threshold_for(quake) -> float:
    """이 지진에 적용할 규모 문턱."""
    return NEAR_MAG if near_korea(quake.lat, quake.lon) else GLOBAL_MAG


def is_notable(quake) -> bool:
    return quake.mag >= threshold_for(quake)


def load_state(path: Path) -> dict:
    """이미 낸 것들. 파일이 없거나 깨졌으면 빈 상태로 시작한다.

    깨진 파일에서 멈추지 않는 이유: 상태 파일이 상한 것 때문에 발행이 통째로
    멎으면, 고칠 사람이 그 사실을 알 길이 없다(무인으로 돈다). 최악은 한 편이
    중복으로 나가는 것이고 그것은 눈에 보인다.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": STATE_VERSION, "published": []}
    if not isinstance(raw, dict):
        return {"version": STATE_VERSION, "published": []}
    published = raw.get("published")
    if not isinstance(published, list):
        published = []
    return {"version": STATE_VERSION, "published": published}


def save_state(path: Path, state: dict) -> None:
    """최근 것만 남긴다 — 이 파일은 커밋되므로 무한히 자라면 안 된다."""
    kept = state.get("published", [])[-200:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": STATE_VERSION, "published": kept},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")


def _last_published_time(state: dict):
    times = []
    for row in state.get("published", []):
        if not isinstance(row, dict):
            continue
        stamp = row.get("published_at")
        if not stamp:
            continue
        try:
            times.append(dt.datetime.fromisoformat(stamp))
        except ValueError:
            continue
    return max(times) if times else None


def pick_event(quakes: list, state: dict, now: dt.datetime):
    """낼 지진 하나, 또는 None. **네트워크도 시계도 타지 않는다** (테스트용).

    돌려주는 것은 `(quake, reason)` 이고 낼 것이 없으면 `(None, reason)` 이다.
    이유를 같이 돌려주는 이유: 무인으로 도는 것이 "아무것도 안 했다"만 남기면
    문턱이 잘못 잡혔는지 조용한 주였는지 구분할 수 없다.
    """
    seen = {row.get("id") for row in state.get("published", [])
            if isinstance(row, dict)}

    fresh = []
    for q in quakes:
        if q.id in seen:
            continue
        if not is_notable(q):
            continue
        age = (now - q.time).total_seconds() / 3600.0
        if age < 0 or age > FRESH_HOURS:
            continue
        fresh.append(q)

    if not fresh:
        return None, "문턱을 넘고 아직 안 낸 지진이 없다"

    best = max(fresh, key=lambda q: q.mag)

    if best.mag < OVERRIDE_MAG:
        last = _last_published_time(state)
        if last is not None:
            since = (now - last).total_seconds() / 3600.0
            if since < COOLDOWN_HOURS:
                return None, (f"냉각 중 — 마지막 발행이 {since:.1f}시간 전이고 "
                              f"{COOLDOWN_HOURS:.0f}시간을 둔다 "
                              f"(대기 중 최대 M{best.mag:.1f})")

    return best, (f"M{best.mag:.1f} {best.place} — 문턱 "
                  f"M{threshold_for(best):.1f}")


def record(state: dict, quake, now: dt.datetime, video_id: str = "") -> dict:
    return record_id(state, quake.id, now, video_id=video_id,
                     mag=quake.mag, place=quake.place,
                     quake_time=quake.time.isoformat())


def record_id(state: dict, quake_id: str, now: dt.datetime, *,
              video_id: str = "", mag=None, place: str = "",
              quake_time: str = "") -> dict:
    """지진 id 만으로도 기록한다. **피드를 다시 읽지 않아도 되게.**

    중복 발행을 막는 데 필요한 것은 id 와 발행 시각뿐이다. 규모·장소는
    사람이 기록을 읽을 때만 쓴다.

    이 경로가 따로 있는 이유: 처음에는 업로드가 끝난 뒤 피드를 다시 받아
    그 지진을 찾아 기록했다. 그러면 **그 두 번째 조회가 실패하는 순간
    기록이 안 남고, 30분 뒤 같은 지진이 또 나간다.** 업로드는 이미
    성공했는데 그것을 적을 길이 없어서 생기는 중복이다.
    """
    state.setdefault("published", []).append({
        "id": quake_id,
        "mag": round(mag, 2) if mag is not None else None,
        "place": place,
        "quake_time": quake_time,
        "published_at": now.isoformat(),
        "video_id": video_id,
    })
    return state
