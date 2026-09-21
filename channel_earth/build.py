"""하루치 지진을 타임랩스 한 편으로 만든다.

    # 숏폼 (세로 9:16, 약 50초)
    python3 channel_earth/build.py --window day

    # 롱폼 (가로 16:9) — 같은 자료로 한 달치를 길게
    python3 channel_earth/build.py --window month --size 1920x1080 --lapse 420

    # 네트워크 없이 렌더만 확인 (가짜 데이터)
    python3 channel_earth/build.py --cache data/fixtures/usgs_day_synthetic.json

두 벌을 뽑는 이유: **숏폼 시청 시간은 파트너 프로그램의 3,000시간에 집계되지
않는다.** 숏폼은 도달에, 롱폼은 시청 시간에 쓴다. 자료도 렌더러도 같아서
한 벌 더 뽑는 비용이 거의 없다.

MoviePy 를 쓰지 않는다. 결국 ffmpeg 래퍼인데, 프레임을 직접 만들어 내는
작업에서는 중간 계층이 느리기만 하다. numpy 배열을 ffmpeg 표준 입력으로
그대로 흘려보낸다 — `channel_sim` 에서 22,000프레임으로 확인한 방식이다.
"""

import argparse
import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import audio, render, sources  # noqa: E402

ROOT = Path(__file__).resolve().parent
BUILD_ROOT = ROOT / "build"

FPS = 30
INTRO_SECONDS = 2.6
OUTRO_SECONDS = 5.4

# 고리가 퍼졌다 사라지는 데 걸리는 시간(영상 기준 초). 이보다 길면 지진이
# 몰린 구간에서 화면이 고리로 덮인다.
RING_LIFE = 0.85
RING_GROWTH = 3.4      # 점 반지름의 몇 배까지 퍼지는가

# 이 아래로는 발행하지 않는다. 피드가 비었거나 파싱이 통째로 실패하면
# 빈 지도만 도는 영상이 나오는데, 그게 조용히 올라가는 것이 제일 나쁘다.
MIN_QUAKES = 20


def dot_radius(mag: float, scale: float) -> float:
    """규모를 점 크기로.

    규모는 로그 눈금이라 그대로 반지름에 넣으면 규모 6이 규모 3의 두 배로만
    보인다 — 실제 에너지는 3만 배다. 그렇다고 에너지에 비례시키면 규모 6
    하나가 화면 절반을 덮는다. 사이에서 타협한 지수다.
    """
    return max(1.6, 1.15 * (1.34 ** max(0.0, mag))) * scale


def parse_size(text: str) -> tuple[int, int]:
    width, _, height = text.lower().partition("x")
    return int(width), int(height)


def hour_counts(quakes: list, start, slots: int = 24) -> list[int]:
    """구간별 건수. 세로 화면 아래의 막대가 이것이다."""
    if not quakes:
        return [0] * slots
    span = max(1.0, (quakes[-1].time - start).total_seconds())
    counts = [0] * slots
    for quake in quakes:
        index = int((quake.time - start).total_seconds() / span * slots)
        counts[min(slots - 1, max(0, index))] += 1
    return counts


def draw_overlay(draw, layout: render.Layout, ctx: dict) -> None:
    """지도 위아래의 모든 글자와 그림. 한 번의 PIL 통과로 끝낸다.

    자리를 화면 높이의 비율로 잡는다. 세로 숏폼과 가로 롱폼이 같은 코드를
    쓰기 때문이고, 한쪽 크기를 바꿀 때마다 좌표를 손보고 싶지 않아서다.
    """
    width, height = layout.width, layout.height
    shown, clock = ctx["shown"], ctx["clock"]
    biggest = max(shown, key=lambda q: q.mag) if shown else None

    if layout.vertical:
        centre = width // 2
        _centred(draw, "지구의 오늘", render.kr_font(int(width * 0.068), bold=True),
                 render.FG, centre, int(height * 0.055))
        _centred(draw, ctx["date_label"], render.kr_font(int(width * 0.030)),
                 render.DIM, centre, int(height * 0.108))
        _centred(draw, clock.strftime("%H:%M UTC"),
                 render.mono_font(int(width * 0.044)), render.ACCENT,
                 centre, int(height * 0.158))

        legend_y = layout.map_y + layout.map_h + int(height * 0.028)
        legend_w = int(width * 0.60)
        render.draw_depth_legend(draw, layout, centre - legend_w // 2,
                                 legend_y, legend_w, int(width * 0.020))
        _centred(draw, "진원 깊이", render.kr_font(int(width * 0.024)),
                 render.DIM, centre, legend_y - int(width * 0.038))

        big = render.mono_font(int(width * 0.085))
        label = render.kr_font(int(width * 0.026))
        num_y = legend_y + int(height * 0.052)
        _centred(draw, f"{len(shown)}", big, render.FG,
                 centre - int(width * 0.21), num_y)
        _centred(draw, "누적 지진", label, render.DIM,
                 centre - int(width * 0.21), num_y + int(width * 0.098))
        _centred(draw, f"{biggest.mag:.1f}" if biggest else "—", big,
                 render.depth_color(biggest.depth_km) if biggest else render.DIM,
                 centre + int(width * 0.21), num_y)
        _centred(draw, "최대 규모", label, render.DIM,
                 centre + int(width * 0.21), num_y + int(width * 0.098))
        if biggest:
            _centred(draw, biggest.place[:32], render.kr_font(int(width * 0.024)),
                     render.DIM, centre, num_y + int(width * 0.155))

        bars_y = num_y + int(height * 0.115)
        bars_w = int(width * 0.78)
        render.draw_hour_bars(draw, layout, ctx["counts"], ctx["slot_done"],
                              centre - bars_w // 2, bars_y, bars_w,
                              int(height * 0.085))
        _centred(draw, ctx["bars_label"], render.kr_font(int(width * 0.024)),
                 render.DIM, centre, bars_y + int(height * 0.095))
        # 출처를 화면에 박는다. 설명란은 접히지만 화면은 접히지 않는다.
        _centred(draw, "자료 USGS Earthquake Hazards Program · 지도 NASA Blue Marble",
                 render.kr_font(int(width * 0.021)), render.GRID,
                 centre, int(height * 0.945))
        return

    right = layout.map_x + layout.map_w + int(width * 0.030)
    title_font = render.kr_font(int(width * 0.034), bold=True)
    draw.text((layout.map_x, int(height * 0.055)), "지구의 오늘",
              font=title_font, fill=render.FG)
    # 제목 너비를 **재서** 날짜를 붙인다. 고정 오프셋으로 두었더니 제목과
    # 겹쳤다 — 글꼴과 글자 수가 바뀌면 그 값은 매번 틀린다.
    box = draw.textbbox((0, 0), "지구의 오늘", font=title_font)
    draw.text((layout.map_x + (box[2] - box[0]) + int(width * 0.020),
               int(height * 0.070)), ctx["date_label"],
              font=render.kr_font(int(width * 0.017)), fill=render.DIM)

    top = layout.map_y
    draw.text((right, top), clock.strftime("%Y-%m-%d %H:%M UTC"),
              font=render.mono_font(int(width * 0.017)), fill=render.ACCENT)
    big = render.mono_font(int(width * 0.050))
    label = render.kr_font(int(width * 0.015))
    draw.text((right, top + int(height * 0.055)), f"{len(shown)}",
              font=big, fill=render.FG)
    draw.text((right, top + int(height * 0.145)), "누적 지진",
              font=label, fill=render.DIM)
    draw.text((right, top + int(height * 0.195)),
              f"{biggest.mag:.1f}" if biggest else "—", font=big,
              fill=render.depth_color(biggest.depth_km) if biggest else render.DIM)
    draw.text((right, top + int(height * 0.285)), "최대 규모",
              font=label, fill=render.DIM)
    if biggest:
        draw.text((right, top + int(height * 0.330)), biggest.place[:24],
                  font=render.kr_font(int(width * 0.014)), fill=render.DIM)

    legend_y = layout.map_y + layout.map_h + int(height * 0.045)
    render.draw_depth_legend(draw, layout, layout.map_x, legend_y,
                             int(layout.map_w * 0.42), int(height * 0.018))
    draw.text((layout.map_x, legend_y - int(height * 0.040)), "진원 깊이",
              font=label, fill=render.DIM)
    bars_w = int(layout.map_w * 0.46)
    bars_x = layout.map_x + layout.map_w - bars_w
    render.draw_hour_bars(draw, layout, ctx["counts"], ctx["slot_done"],
                          bars_x, legend_y, bars_w, int(height * 0.050))
    draw.text((bars_x, legend_y - int(height * 0.040)), ctx["bars_label"],
              font=label, fill=render.DIM)
    draw.text((layout.map_x, int(height * 0.945)),
              "자료 USGS Earthquake Hazards Program · 지도 NASA Blue Marble",
              font=render.kr_font(int(width * 0.014)), fill=render.GRID)


def _centred(draw, text: str, font, color, cx: int, y: int) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (box[2] - box[0]) / 2, y), text, font=font, fill=color)


def draw_lines(draw, lines) -> None:
    """카드용. (글, 폰트, 색, x, y, 가운데정렬) 목록을 그대로 그린다."""
    for text, font, color, x, y, centred in lines:
        if centred:
            box = draw.textbbox((0, 0), text, font=font)
            x = x - (box[2] - box[0]) / 2
        draw.text((x, y), text, font=font, fill=color)


def card(layout: render.Layout, lines: list[tuple]) -> np.ndarray:
    """여는 카드와 닫는 카드. 지도 없이 글자만."""
    frame = np.zeros((layout.height, layout.width, 3), dtype=np.uint8)
    frame[:] = render.BG
    text, mask = render.text_layer(layout, lambda d: draw_lines(d, lines))
    render.blit_text(frame, text, mask)
    return frame


def intro_card(layout: render.Layout, quakes: list, window: str) -> np.ndarray:
    first, last = quakes[0].time, quakes[-1].time
    centre = layout.width // 2
    title = render.kr_font(int(layout.width * 0.072), bold=True)
    sub = render.kr_font(int(layout.width * 0.030))
    mono = render.mono_font(int(layout.width * 0.028))
    y = layout.height // 2 - int(layout.height * 0.12)
    step = int(layout.width * 0.062)
    return card(layout, [
        ("지구의 오늘", title, render.FG, centre, y, True),
        (f"{first:%Y-%m-%d %H:%M} ~ {last:%m-%d %H:%M} UTC", mono,
         render.ACCENT, centre, y + step + int(layout.width * 0.02), True),
        (f"관측된 지진 {len(quakes)}건", sub, render.FG,
         centre, y + step * 2 + int(layout.width * 0.02), True),
        ("색은 깊이 · 크기는 규모 · 소리는 그 둘", sub, render.DIM,
         centre, y + step * 2 + int(layout.width * 0.075), True),
        ("자료: USGS 지진 피드", sub, render.DIM,
         centre, y + step * 2 + int(layout.width * 0.135), True),
    ])


def outro_card(layout: render.Layout, quakes: list) -> np.ndarray:
    top5 = sorted(quakes, key=lambda q: -q.mag)[:5]
    centre = layout.width // 2
    head = render.kr_font(int(layout.width * 0.050), bold=True)
    mono = render.mono_font(int(layout.width * 0.034))
    place = render.kr_font(int(layout.width * 0.026))
    y = layout.height // 2 - int(layout.height * 0.15)
    lines = [("가장 컸던 다섯", head, render.FG, centre, y, True)]
    y += int(layout.width * 0.10)
    for quake in top5:
        lines.append((f"M {quake.mag:.1f}", mono,
                      render.depth_color(quake.depth_km),
                      centre - int(layout.width * 0.26), y, True))
        lines.append((f"{quake.place[:26]}  ·  {quake.depth_km:.0f}km", place,
                      render.DIM, centre + int(layout.width * 0.08), y + 6, True))
        y += int(layout.width * 0.062)
    return card(layout, lines)


def render_video(quakes: list, layout: render.Layout, lapse: float,
                 window: str, out_dir: Path) -> tuple[Path, float]:
    total_seconds = INTRO_SECONDS + lapse + OUTRO_SECONDS

    base = render.base_frame(layout)
    persistent = np.zeros((layout.height, layout.width, 3), dtype=np.float32)
    scale = layout.map_w / 1080.0

    t0, t1 = quakes[0].time, quakes[-1].time
    span = max(1.0, (t1 - t0).total_seconds())

    # 지진마다 "영상에서 몇 초에 나오는가"를 미리 계산한다. 프레임 루프
    # 안에서 매번 시간 계산을 다시 하면 프레임당 300번이 된다.
    schedule = [(INTRO_SECONDS + (q.time - t0).total_seconds() / span * lapse, q)
                for q in quakes]

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        silent = out_dir / "silent.mp4"
        proc = subprocess.Popen(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{layout.width}x{layout.height}", "-r", str(FPS), "-i", "-",
             "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-pix_fmt", "yuv420p", str(silent)],
            stdin=subprocess.PIPE)

        intro = intro_card(layout, quakes, window)
        for _ in range(int(INTRO_SECONDS * FPS)):
            proc.stdin.write(intro.tobytes())

        placed = 0
        shown: list = []
        ring_layer = np.zeros_like(persistent)
        slots = 24 if window in ("day", "hour") else 30
        counts = hour_counts(quakes, t0, slots)
        bars_label = ("시간대별 건수 (UTC)" if window in ("day", "hour")
                      else "기간별 건수")
        date_label = (f"{t0:%Y-%m-%d} UTC" if window in ("day", "hour")
                      else f"{t0:%Y-%m-%d} ~ {t1:%m-%d} UTC")
        ctx = {"shown": shown, "clock": t0, "counts": counts,
               "slot_done": -1.0, "date_label": date_label,
               "bars_label": bars_label}
        text, mask = render.text_layer(layout, lambda d: draw_overlay(d, layout, ctx))

        for number in range(int(lapse * FPS)):
            now_video = INTRO_SECONDS + number / FPS
            progress = number / max(1, int(lapse * FPS))
            clock = t0 + dt.timedelta(seconds=progress * span)

            while placed < len(schedule) and schedule[placed][0] <= now_video:
                _, quake = schedule[placed]
                placed += 1
                shown.append(quake)
                if not layout.on_map(quake.lat):
                    # 잘라 낸 위도 밖이다. 숫자에는 넣되 지도에는 못 그린다.
                    continue
                x, y = layout.project(quake.lon, quake.lat)
                render.add_dot(persistent, x, y, dot_radius(quake.mag, scale),
                               render.depth_color(quake.depth_km), 0.92)

            ring_layer[:] = 0.0
            for at, quake in schedule[max(0, placed - 40):placed]:
                age = now_video - at
                if not (0.0 <= age < RING_LIFE) or not layout.on_map(quake.lat):
                    continue
                t = age / RING_LIFE
                x, y = layout.project(quake.lon, quake.lat)
                radius = dot_radius(quake.mag, scale) * (1 + RING_GROWTH * t)
                render.add_ring(ring_layer, x, y, radius, 2.0 * scale + 1.0,
                                render.depth_color(quake.depth_km),
                                (1.0 - t) ** 1.6)

            frame = render.composite(base, persistent, ring_layer)

            # 글자는 초당 열 번만 다시 그린다. 매 프레임 PIL 을 부를 이유가 없다.
            if number % 3 == 0:
                ctx["clock"] = clock
                ctx["slot_done"] = progress * slots
                text, mask = render.text_layer(
                    layout, lambda d: draw_overlay(d, layout, ctx))
            render.blit_text(frame, text, mask)
            proc.stdin.write(frame.tobytes())

        outro = outro_card(layout, quakes)
        for _ in range(int(OUTRO_SECONDS * FPS)):
            proc.stdin.write(outro.tobytes())

        proc.stdin.close()
        proc.wait()

        # 소리. 지진 하나가 소리 하나다.
        buffer = np.zeros(int(total_seconds * audio.RATE) + audio.RATE,
                          dtype=np.float64)
        audio.drone(buffer)
        for at, quake in schedule:
            audio.strike(buffer, at, audio.pitch_for_depth(quake.depth_km),
                         audio.level_for_magnitude(quake.mag),
                         decay=0.35 + 0.16 * max(0.0, quake.mag - 3.0))
        pcm = work / "audio.raw"
        pcm.write_bytes(audio.to_pcm16(buffer))

        final = out_dir / "video.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-i", str(silent),
             "-f", "s16le", "-ar", str(audio.RATE), "-ac", "1", "-i", str(pcm),
             "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
             "-movflags", "+faststart", str(final)],
            check=True)
        silent.unlink()

    return final, total_seconds


def build_description(quakes: list, window: str, synthetic: bool) -> str:
    top = sorted(quakes, key=lambda q: -q.mag)[:5]
    first, last = quakes[0].time, quakes[-1].time
    lines = [
        f"{first:%Y년 %m월 %d일} {first:%H:%M}부터 {last:%m월 %d일} "
        f"{last:%H:%M}까지(UTC) 관측된 지진 {len(quakes)}건입니다.",
        "점의 색은 진원 깊이, 크기는 규모, 소리의 높이와 크기도 그 둘에서 나옵니다.",
        "",
        "가장 컸던 다섯",
    ]
    lines += [f"M {q.mag:.1f}  {q.place}  (깊이 {q.depth_km:.0f}km)" for q in top]
    lines += [
        "",
        f"M4.0 이상 {sum(1 for q in quakes if q.mag >= 4):,}건 · "
        f"M5.0 이상 {sum(1 for q in quakes if q.mag >= 5):,}건",
        "",
        "지도에서 미국 쪽 점이 유독 많은 것은 그곳에 지진이 많아서가 아니라",
        "관측망이 촘촘해 아주 작은 지진까지 잡히기 때문입니다.",
        "",
        "자료: USGS Earthquake Hazards Program (earthquake.usgs.gov)",
        "지도: NASA Blue Marble",
        "",
        "#지진 #지구과학 #데이터시각화 #USGS #실시간데이터",
    ]
    if synthetic:
        lines.insert(0, "※ 이 영상은 가짜 데이터로 만든 렌더 확인용입니다. "
                        "실제 지진 정보가 아닙니다.")
    return "\n".join(lines)


def verify_publishable(meta: dict) -> None:
    """발행해도 되는 상태인가.

    가짜 데이터로 만든 빌드를 막는 것이 이 함수의 첫 번째 일이다. 지진
    정보를 사실처럼 내보내는 것은 그 자체로 해가 된다.
    """
    problems = []
    if meta.get("synthetic"):
        problems.append("가짜 데이터(픽스처)로 만든 빌드다. 실제 지진 정보가 "
                        "아니므로 발행하지 않는다")
    if meta.get("quake_count", 0) < MIN_QUAKES:
        problems.append(f"지진이 {meta.get('quake_count', 0)}건뿐이다. 피드가 "
                        "비었거나 파싱이 실패했을 때 이렇게 된다")
    if meta.get("duration_seconds", 0) < 15:
        problems.append("영상이 너무 짧다. 렌더가 중간에 끊겼다")
    for field in ("title", "description"):
        if not (meta.get(field) or "").strip():
            problems.append(f"{field} 가 비어 있다")
    if problems:
        raise SystemExit("발행하지 않는다:\n  - " + "\n  - ".join(problems))


def main() -> int:
    parser = argparse.ArgumentParser(description="하루치 지진을 타임랩스로")
    parser.add_argument("--window", default="day",
                        choices=sorted(sources.FEEDS), help="받을 기간")
    parser.add_argument("--size", default="1080x1920",
                        help="세로 숏폼 1080x1920 / 가로 롱폼 1920x1080")
    parser.add_argument("--lapse", type=float, default=42.0,
                        help="타임랩스 본편 길이(초)")
    parser.add_argument("--cache", type=Path,
                        help="이 파일을 쓰고 네트워크를 타지 않는다")
    parser.add_argument("--dump", type=Path, help="받은 응답을 그대로 적는다")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    quakes = sources.load_quakes(args.window, cache=args.cache, dump=args.dump)
    if not quakes:
        raise SystemExit("지진이 한 건도 없다. 피드를 확인할 것")

    # 픽스처는 파일 이름으로 알아본다. 이름을 바꿔 가며 발행하려 들면
    # 막을 방법이 없지만, 실수로 나가는 것은 이것으로 걸린다.
    synthetic = bool(args.cache and "synthetic" in args.cache.name)

    width, height = parse_size(args.size)
    layout = render.Layout.for_size(width, height)

    today = dt.date.today().isoformat()
    shape = "short" if layout.vertical else "long"
    out_dir = args.out or BUILD_ROOT / f"{today}-{args.window}-{shape}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[build] {len(quakes)}건 · {width}x{height} · "
          f"타임랩스 {args.lapse:.0f}초", file=sys.stderr)
    video, seconds = render_video(quakes, layout, args.lapse, args.window, out_dir)

    first, last = quakes[0].time, quakes[-1].time
    meta = {
        "window": args.window,
        "shape": shape,
        "title": f"지구의 오늘 — {first:%m월 %d일} 지진 {len(quakes)}건",
        "description": build_description(quakes, args.window, synthetic),
        "tags": ["지진", "지구과학", "데이터시각화", "USGS", "실시간데이터",
                 "earthquake"],
        "categoryId": "28",
        "privacyStatus": "private",
        "quake_count": len(quakes),
        "max_magnitude": max(q.mag for q in quakes),
        "window_start": first.isoformat(),
        "window_end": last.isoformat(),
        "duration_seconds": round(seconds, 2),
        "synthetic": synthetic,
    }
    if not synthetic:
        verify_publishable(meta)
    else:
        print("[build] 가짜 데이터로 만든 빌드다 — 발행 금지 표시를 남긴다",
              file=sys.stderr)

    (out_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[build] {video} — {seconds:.0f}초", file=sys.stderr)
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
