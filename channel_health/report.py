"""metrics.csv 를 읽어 "무엇이 부족한가"를 한국어로 적는다.

숫자를 늘어놓지 않고 **행동으로 이어지는 것만** 적는다. 매주 같은 표가
올라오면 아무도 안 읽고, 안 읽히는 보고서는 없는 것과 같다.

말할 수 없는 것을 분명히 해 둔다. 여기 있는 것은 조회수·좋아요·댓글 수다.
**시청 시간이 아니다.** 파트너 프로그램의 3,000시간은 Analytics API 에 있고
지금 토큰으로는 못 읽는다. 조회수가 늘었다고 시청 시간이 늘었다고 적지 말 것 —
숏폼은 조회수가 잘 늘고 시청 시간에는 안 들어간다. 정확히 반대로 읽힌다.
"""

import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import channels as channel_registry

ROOT = Path(__file__).resolve().parent
METRICS_PATH = ROOT / "metrics.csv"

# 숏폼·롱폼을 가르는 우리 기준. 유튜브의 분류와 정확히 같다고 보지 말 것 —
# 보고서를 읽기 위한 칸막이지 채널 설정이 아니다.
SHORT_MAX_SECONDS = 180

# 낸 지 이만큼 지났는데도 조회수가 0 이면 짚는다. 너무 짧게 잡으면 어제
# 올린 것까지 실패로 세고, 너무 길게 잡으면 손쓸 시점을 놓친다.
DEAD_AFTER_DAYS = 7

# 최근 몇 편을 "요즘"으로 볼 것인가.
RECENT_COUNT = 5

# 부진으로 볼 기준, 그리고 견줄 예전 편이 최소 몇 편은 있어야 하는가.
#
# 2 는 낮다 — 두 편의 중앙값은 그냥 평균이라 한 편만 튀어도 흔들린다. 그래도
# 2 로 둔 이유는 이 검사가 가장 필요한 채널이 가장 작기 때문이다. 3 으로
# 잡았더니 영상 7편짜리 머니로직에서는 영영 켜지지 않았다(최근 5편을 빼면
# 2편만 남는다). 사람에게 "되짚어 보라"고 말하는 문장이지 무언가를 자동으로
# 바꾸는 신호가 아니라서, 늦게 켜지는 쪽보다 가끔 헛짚는 쪽을 택했다.
SLUMP_RATIO = 0.5
BASELINE_MIN = 2

# 롱폼이 숏폼의 이만큼도 안 눌리면 짚는다. 롱폼이 덜 눌리는 것 자체는
# 정상이라 기준을 낮게 잡는다 — 매주 울리는 경고는 안 읽힌다.
LONGFORM_LAG_RATIO = 0.25
LONGFORM_MIN_FOR_COMPARISON = 2


def load_rows(path=METRICS_PATH):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _int(value):
    """빈 칸은 None. 0 과 구별한다."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _when(value):
    text = (value or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def snapshots(rows, channel_name):
    """이 채널의 스냅샷 시각을 오래된 순으로."""
    return sorted({row["observed_at"] for row in rows
                   if row.get("channel") == channel_name})


def at_snapshot(rows, channel_name, observed_at):
    return [row for row in rows if row.get("channel") == channel_name
            and row.get("observed_at") == observed_at]


def is_short(row):
    seconds = _int(row.get("duration_s"))
    # 길이를 모르면 롱폼으로 둔다. 숏폼으로 잘못 넣으면 롱폼 통계가
    # 조용히 얇아지는데, 롱폼 쪽이 이 채널들이 보려는 숫자다.
    return seconds is not None and seconds <= SHORT_MAX_SECONDS


def _median(numbers):
    ordered = sorted(numbers)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _views(rows):
    return [value for value in (_int(row.get("views")) for row in rows)
            if value is not None]


def channel_findings(rows, channel, now):
    """한 채널에서 짚을 것들. 없으면 빈 목록."""
    stamps = snapshots(rows, channel.name)
    if not stamps:
        return ["기록이 없다. 아직 한 번도 수집되지 않았다."]

    latest = at_snapshot(rows, channel.name, stamps[-1])
    findings = []

    shorts = [row for row in latest if is_short(row)]
    longs = [row for row in latest if not is_short(row)]
    short_median = _median(_views(shorts))
    long_median = _median(_views(longs))

    parts = [f"영상 {len(latest)}편(숏폼 {len(shorts)} · 롱폼 {len(longs)})"]
    if short_median is not None:
        parts.append(f"숏폼 조회수 중앙값 {short_median:g}")
    if long_median is not None:
        parts.append(f"롱폼 조회수 중앙값 {long_median:g}")
    findings.append(" · ".join(parts))

    # 낸 지 한참 됐는데 아무도 안 본 것
    cutoff = now - timedelta(days=DEAD_AFTER_DAYS)
    dead = [row for row in latest
            if _int(row.get("views")) == 0
            and (_when(row.get("published_at")) or now) < cutoff]
    if dead:
        titles = ", ".join(f"{row['title'][:28]}" for row in dead[:3])
        more = f" 외 {len(dead) - 3}편" if len(dead) > 3 else ""
        findings.append(
            f"**{DEAD_AFTER_DAYS}일이 지나도 조회수 0 인 영상 {len(dead)}편** — {titles}{more}. "
            "제목·썸네일이 안 걸렸거나 노출 자체가 안 됐다.")

    # 롱폼이 이 채널의 시청 시간 경로다. 안 눌리면 경로가 없는 것과 같다.
    if (len(longs) >= LONGFORM_MIN_FOR_COMPARISON and short_median
            and long_median is not None
            and long_median < short_median * LONGFORM_LAG_RATIO):
        findings.append(
            f"롱폼 중앙값({long_median:g})이 숏폼({short_median:g})의 "
            f"{LONGFORM_LAG_RATIO:.0%}에 못 미친다. 롱폼이 적게 눌리는 것 자체는 "
            "당연하지만, 시청 시간을 쌓는 자리는 롱폼뿐이라 여기가 막히면 "
            "숏폼을 아무리 올려도 3,000시간은 그대로다.")

    # 요즘 낸 것이 예전만 못한가
    #
    # **기준을 최근 편들과 겹치게 잡지 않는다.** 전체 중앙값에는 최근 편이
    # 같이 들어 있어서, 영상이 적은 채널에서는 최근 편이 기준을 자기 쪽으로
    # 끌어내린다. 실제로 7편 중 4편이 부진한 자료를 넣었더니 이 검사가
    # 조용히 지나갔다. 최근 것을 뺀 나머지와 견준다.
    dated = [row for row in latest if _when(row.get("published_at"))]
    dated.sort(key=lambda row: _when(row["published_at"]), reverse=True)
    recent, earlier = dated[:RECENT_COUNT], dated[RECENT_COUNT:]
    recent_median = _median(_views(recent))
    earlier_median = _median(_views(earlier))
    if (len(earlier) >= BASELINE_MIN and recent_median is not None
            and earlier_median and recent_median < earlier_median * SLUMP_RATIO):
        findings.append(
            f"최근 {len(recent)}편 조회수 중앙값({recent_median:g})이 "
            f"그 이전({earlier_median:g})의 {SLUMP_RATIO:.0%}에 못 미친다. "
            "최근 바꾼 것을 되짚을 것.")

    # 발행이 끊겼나
    if dated:
        newest = _when(dated[0]["published_at"])
        idle = (now - newest).days
        if idle >= 3:
            findings.append(f"마지막 발행이 {idle}일 전이다. 파이프라인이 도는지 볼 것.")

    # 늘고 있나 — 스냅샷이 둘 이상일 때만
    if len(stamps) >= 2:
        before = at_snapshot(rows, channel.name, stamps[-2])
        gained = sum(_views(latest)) - sum(_views(before))
        then, now_stamp = _when(stamps[-2]), _when(stamps[-1])
        days = (now_stamp - then).days if then and now_stamp else 0
        span = f"약 {days}일 사이" if days else "간격을 읽지 못했다"
        findings.append(f"직전 기록 이후 조회수 합계 {gained:+d} ({span}).")
    else:
        findings.append(
            "스냅샷이 하나뿐이라 증감을 말할 수 없다. 다음 회차부터 나온다.")

    return findings


def build(rows, now=None, registry=channel_registry.CHANNELS):
    now = now or datetime.now(timezone.utc)
    lines = [f"# 채널 상태 — {now.strftime('%Y-%m-%d')}", ""]
    for channel in registry:
        lines.append(f"## {channel.label}")
        for finding in channel_findings(rows, channel, now):
            lines.append(f"- {finding}")
        lines.append("")
    lines += [
        "---",
        "",
        "이 숫자는 **조회수이지 시청 시간이 아니다.** 파트너 프로그램이 세는 "
        "3,000시간은 Analytics API 에 있고 지금 토큰으로는 읽지 못한다. "
        "숏폼은 조회수가 잘 늘면서 그 3,000시간에는 들어가지 않으므로, "
        "숏폼 조회수가 올랐다고 수익화가 가까워졌다고 읽으면 정확히 반대다.",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--metrics-path", default=str(METRICS_PATH))
    parser.add_argument("--out", help="적을 파일. 없으면 화면으로")
    args = parser.parse_args(argv)

    text = build(load_rows(args.metrics_path))
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"보고서: {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
