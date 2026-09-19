"""수익화 요건까지 얼마나 남았는지 추정한다.

필수조건 6번이 겨누는 곳이 결국 여기다. 그런데 그때까지 이 저장소에서
"수익화에 얼마나 가까운가"를 말할 수 있는 것은 `channel_200y3b/scripts/
channel_fix.py` 의 `cmd_status` 뿐이었고, 그것은 **손으로 돌려야** 하고
**@200-y3b 한 채널만** 본다. 매주 자동으로 도는 자리에 같은 계산이 필요했다.

요건 표의 원본은 channel_fix.py 의 cmd_status 다. 여기 사본을 두는 이유는
`channel_health` 가 다른 프로젝트를 import 하지 않기 때문이다(CLAUDE.md).

**여기서 내는 시청 시간은 추정치다. 유튜브가 세는 값이 아니다.**
Data API 에는 시청 시간이 없어서 `조회수 × 길이 × 가정 시청률` 로 짐작한다.
오차는 한쪽으로만 나지 않는다:

- 가정 시청률이 실제보다 높으면 **부풀려진다.** 그래서 한 값이 아니라
  구간으로 낸다.
- 12개월보다 전에 올린 영상이 이번 달에 받은 조회수는 유튜브 기준으로는
  집계에 들어가지만 여기서는 통째로 빠진다. 이쪽은 **모자라게 나온다.**

두 오차가 서로를 상쇄한다고 볼 근거가 없으므로, 이 숫자로 "이제 곧 된다"를
판단하지 말 것. 실측은 `yt-analytics.readonly` 스코프를 받아야 열린다.

**읽기만 한다.**
"""

from dataclasses import dataclass
from datetime import timedelta

import rows as row_tools

# 유튜브가 세는 창. 시청 시간은 최근 12개월, 숏폼 조회수는 최근 90일이다.
WATCH_WINDOW_DAYS = 365
SHORTS_WINDOW_DAYS = 90

# 최근 90일 공개 업로드 요건.
UPLOADS_WINDOW_DAYS = 90
UPLOADS_REQUIRED = 3

# 가정 시청률의 구간.
#
# 한 값으로 내면 그 값이 사실처럼 읽힌다. 아래를 20% 로 잡은 것은 긴 영상의
# 평균 시청 지속 시간이 그보다 낮은 경우도 흔해서 "최소한 이만큼"이라는
# 뜻이 아니라는 점을 분명히 하기 위해서다. channel_fix.py 는 50%·35%·20%
# 세 값을 찍는데, 보고서에는 50% 를 뺐다 — 낙관적인 숫자가 맨 위에 있으면
# 그것만 기억에 남는다.
RETENTION_LOW = 0.20
RETENTION_HIGH = 0.35


@dataclass(frozen=True)
class Tier:
    """수익화 단계 하나. 구독자와 (시청 시간 또는 숏폼 조회수)를 함께 채워야 한다."""

    label: str
    subscribers: int
    watch_hours: int
    shorts_views: int


# channel_fix.py cmd_status 의 표와 같은 값이다. 유튜브가 요건을 바꾸면
# 두 곳을 같이 고쳐야 한다.
TIERS = (
    Tier("초기 수익 창출 (팬 후원·쇼핑)", 500, 3_000, 3_000_000),
    Tier("정식 파트너 (광고 수익)", 1_000, 4_000, 10_000_000),
)


@dataclass(frozen=True)
class Standing:
    """한 채널이 지금 서 있는 자리."""

    subscribers: int | None
    hours_low: float
    hours_high: float
    longform_12mo: int
    shorts_views_90d: int
    uploads_90d: int
    has_metrics: bool
    # 한 번도 수집되지 않은 것과, 수집은 됐는데 구독자가 비공개인 것은 다르다.
    # 섞으면 구독자를 숨긴 채널에 "기록이 없다"고 적는다.
    has_stats: bool

    def hours_short_of(self, target):
        """목표까지 모자란 시청 시간을 (낙관, 비관) 순으로."""
        return max(0.0, target - self.hours_high), max(0.0, target - self.hours_low)

    def subscribers_short_of(self, target):
        if self.subscribers is None:
            return None
        return max(0, target - self.subscribers)


def _watch_hours(video_rows, retention):
    """조회수 × 길이 × 가정 시청률, 시간 단위."""
    total = 0
    for row in video_rows:
        views = row_tools.as_int(row.get("views"))
        seconds = row_tools.as_int(row.get("duration_s"))
        if views is None or seconds is None:
            continue
        total += views * seconds
    return total * retention / 3600


def standing(metric_rows, stats_rows, channel_name, now):
    """이 채널의 현재 위치. metrics.csv 가 비어도 구독자만으로 답한다."""
    latest = row_tools.latest_snapshot(metric_rows, channel_name)
    stats = row_tools.latest_snapshot(stats_rows, channel_name)
    subscribers = row_tools.as_int(stats[-1].get("subscribers")) if stats else None

    watch_cut = now - timedelta(days=WATCH_WINDOW_DAYS)
    shorts_cut = now - timedelta(days=SHORTS_WINDOW_DAYS)
    uploads_cut = now - timedelta(days=UPLOADS_WINDOW_DAYS)

    def published(row):
        return row_tools.when(row.get("published_at"))

    # 발행일을 모르는 줄은 창 안에 넣지 않는다. 넣으면 몇 년 전 영상이
    # 이번 12개월 몫으로 잡혀 남은 거리가 실제보다 가깝게 나온다.
    dated = [(row, published(row)) for row in latest]
    dated = [(row, at) for row, at in dated if at is not None]

    longform_12mo = [row for row, at in dated
                     if at >= watch_cut and not row_tools.is_short(row)]
    shorts_90 = [row for row, at in dated
                 if at >= shorts_cut and row_tools.is_short(row)]
    uploads_90 = [row for row, at in dated if at >= uploads_cut]

    return Standing(
        subscribers=subscribers,
        hours_low=_watch_hours(longform_12mo, RETENTION_LOW),
        hours_high=_watch_hours(longform_12mo, RETENTION_HIGH),
        longform_12mo=len(longform_12mo),
        shorts_views_90d=sum(row_tools.views(shorts_90)),
        uploads_90d=len(uploads_90),
        has_metrics=bool(latest),
        has_stats=bool(stats),
    )


def _nearest_gap(place, tier):
    """이 단계에서 무엇이 더 먼가 — 구독자인가 시청 시간인가.

    남은 양을 목표 대비 비율로 견준다. "373명 부족"과 "2,950시간 부족"은
    단위가 달라 그냥은 비교되지 않는다.
    """
    short_subs = place.subscribers_short_of(tier.subscribers)
    if short_subs is None:
        return None
    subs_ratio = short_subs / tier.subscribers
    # 비관 쪽(시청률 20%)으로 견준다. 낙관 쪽으로 견주면 "시청 시간은 거의
    # 다 됐다"고 말해 놓고 다음 주에 뒤집히는 일이 생긴다.
    hours_ratio = place.hours_short_of(tier.watch_hours)[1] / tier.watch_hours
    if subs_ratio == 0 and hours_ratio == 0:
        return None
    return "구독자" if subs_ratio > hours_ratio else "시청 시간"


def lines(place):
    """보고서에 넣을 한국어 줄들."""
    if not place.has_stats and not place.has_metrics:
        return ["수집된 기록이 없어 수익화 거리를 낼 수 없다."]

    out = []
    # 숨긴 것과 아직 안 읽은 것은 다르다. 둘 다 "비공개"로 적으면, 구독자
    # 수집이 빠진 채로 도는 동안에도 채널이 숨긴 것처럼 보여 아무도 안 고친다.
    if place.subscribers is not None:
        subs = f"{place.subscribers:,}명"
    elif place.has_stats:
        subs = "비공개"
    else:
        subs = "아직 수집 전"
    out.append(
        f"구독자 {subs} · 최근 12개월 롱폼 {place.longform_12mo}편 · "
        f"최근 90일 숏폼 조회수 {place.shorts_views_90d:,}회")

    ok = "충족" if place.uploads_90d >= UPLOADS_REQUIRED else "미충족"
    out.append(f"최근 90일 공개 업로드 {place.uploads_90d}편 "
               f"({UPLOADS_REQUIRED}편 요건 {ok})")

    out.append(
        f"롱폼 시청 시간 **추정** {place.hours_low:,.0f}~{place.hours_high:,.0f}시간 "
        f"(시청률 {RETENTION_LOW:.0%}~{RETENTION_HIGH:.0%} 가정). "
        "유튜브가 세는 값이 아니다 — 아래 주의를 볼 것.")

    for tier in TIERS:
        short_subs = place.subscribers_short_of(tier.subscribers)
        low, high = place.hours_short_of(tier.watch_hours)
        bits = []
        if short_subs is None:
            bits.append("구독자 비공개" if place.has_stats else "구독자 미수집")
        elif short_subs:
            bits.append(f"구독자 {short_subs:,}명 부족")
        else:
            bits.append("구독자 충족")
        if high:
            bits.append(f"시청 시간 {low:,.0f}~{high:,.0f}시간 부족")
        else:
            bits.append("시청 시간 추정으로는 충족")
        line = f"**{tier.label}** — " + " · ".join(bits)
        blocker = _nearest_gap(place, tier)
        if blocker:
            line += f" → 지금 더 먼 쪽은 **{blocker}**"
        out.append(line)

    if place.shorts_views_90d and place.longform_12mo == 0:
        out.append(
            "숏폼만 있고 최근 12개월 롱폼이 없다. 숏폼 조회수로 가는 길"
            f"({TIERS[0].shorts_views:,}회/90일)은 지금 속도로 닿는 숫자가 "
            "아니므로, 시청 시간 쪽이 사실상 유일한 경로다.")
    return out
