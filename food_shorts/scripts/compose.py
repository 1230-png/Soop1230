"""Turn downloaded cooking footage into a food-styling Shorts.

Every scene is real moving video — chopping, sizzling, sauce pouring — cut
to length, filled to the 9:16 canvas, graded, and stamped with the channel's
subtitle furniture. There is deliberately no still-image path: a Shorts that
holds on a photo reads as a slideshow, which is exactly what this replaces.

Source clips arrive at whatever resolution, framerate, aspect and length the
uploader happened to use, so each one is normalised before it can be joined
to the next; concatenating mismatched streams is the usual way these
pipelines produce a video that plays for one scene and then freezes.
"""

import json
import random
import subprocess
import sys
from pathlib import Path

WIDTH, HEIGHT = 1080, 1920
FPS = 30

# Slightly warm, slightly contrastier than source. Free stock kitchen footage
# is usually shot flat, and food needs saturation to look worth eating.
GRADE = "eq=contrast=1.09:saturation=1.22:gamma=0.98,colorbalance=rm=0.04:bm=-0.03"


def probe(path):
    """Duration and dimensions of a clip, or None if ffprobe rejects it."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            check=True, capture_output=True,
        )
        data = json.loads(out.stdout.decode())
    except Exception:  # noqa: BLE001 - a bad download must not raise
        return None

    video = next((s for s in data.get("streams", [])
                  if s.get("codec_type") == "video"), None)
    if not video:
        return None

    try:
        duration = float(data.get("format", {}).get("duration", 0)) or 0.0
    except (TypeError, ValueError):
        duration = 0.0

    return {
        "duration": duration,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "has_audio": any(s.get("codec_type") == "audio"
                         for s in data.get("streams", [])),
    }


def pick_start(source_duration, want, seed=""):
    """Where to cut into a clip.

    Stock footage often opens on a slate or an empty counter, so skip the
    head when the clip is long enough to afford it, and vary the offset so
    two videos built from the same clip do not open on the same frame.
    """
    slack = source_duration - want
    if slack <= 0.4:
        return 0.0
    head = min(0.6, slack * 0.25)
    rng = random.Random(seed)
    return round(head + rng.random() * max(slack - head, 0.0) * 0.8, 2)


def make_scene(src, overlay_png, duration, out_path, seed="", speed=1.0):
    """One finished scene: footage filled to 9:16, graded, overlay burned in.

    `speed` under 1.0 slows the clip, which is how food videos sell a pour or
    a sizzle; the trim is taken from the sped-up timeline so the scene still
    lands on `duration`.
    """
    info = probe(src)
    if not info or info["width"] <= 0:
        print(f"  [warn] 클립을 읽을 수 없음: {Path(src).name}", file=sys.stderr)
        return False

    need_src = duration * speed
    start = pick_start(info["duration"], need_src, seed) if info["duration"] else 0.0

    # Loop short clips instead of freezing on the last frame. -stream_loop
    # needs the input rewound, so it goes before -i.
    loop = ["-stream_loop", "-1"] if info["duration"] and info["duration"] < need_src else []

    chain = (
        # Fill the vertical canvas: scale so both axes cover, then centre-crop.
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={WIDTH}:{HEIGHT},"
        f"{GRADE},"
        f"setsar=1,fps={FPS}"
    )
    if abs(speed - 1.0) > 0.01:
        chain += f",setpts={1 / speed:.4f}*PTS"

    cmd = ["ffmpeg", "-y", "-v", "error"]
    if start > 0:
        cmd += ["-ss", f"{start:.2f}"]
    cmd += loop + ["-i", str(src)]

    if overlay_png is not None:
        cmd += ["-i", str(overlay_png)]
        graph = (
            f"[0:v]{chain}[bg];"
            f"[1:v]format=rgba[ov];"
            f"[bg][ov]overlay=0:0:format=auto[v]"
        )
    else:
        graph = f"[0:v]{chain}[v]"

    cmd += [
        "-filter_complex", graph,
        "-map", "[v]",
        "-an",
        "-t", f"{duration:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        str(out_path),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip().splitlines()
        print(f"  [warn] 장면 합성 실패: {detail[-1] if detail else exc}", file=sys.stderr)
        return False

    # A clip whose source ran out mid-encode is worse than no clip: it would
    # silently shorten the video and slide the audio off the steps.
    result = probe(out_path)
    if not result or result["duration"] < duration - 0.15:
        got = result["duration"] if result else 0
        print(f"  [warn] 장면이 짧게 끝남 ({got:.1f}s < {duration:.1f}s)", file=sys.stderr)
        return False
    return True


def concat(clip_paths, out_path, fade=0.4):
    """Chain scenes with xfade so cuts dissolve instead of snapping."""
    clips = [Path(p) for p in clip_paths]
    if not clips:
        return False
    if len(clips) == 1:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(clips[0]),
                        "-c", "copy", str(out_path)], check=True, capture_output=True)
        return True

    durations = []
    for clip in clips:
        info = probe(clip)
        if not info:
            return False
        durations.append(info["duration"])

    cmd = ["ffmpeg", "-y", "-v", "error"]
    for clip in clips:
        cmd += ["-i", str(clip)]

    # Each xfade overlaps its pair by `fade`, so every later offset has to
    # subtract the overlap already spent upstream.
    steps, prev, elapsed = [], "[0:v]", durations[0]
    for i in range(1, len(clips)):
        offset = max(elapsed - fade, 0.0)
        label = "[v]" if i == len(clips) - 1 else f"[x{i}]"
        steps.append(
            f"{prev}[{i}:v]xfade=transition=fade:duration={fade}:offset={offset:.3f}{label}"
        )
        prev = label
        elapsed = offset + durations[i]

    cmd += [
        "-filter_complex", ";".join(steps),
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        str(out_path),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip().splitlines()
        print(f"  [warn] 장면 이어붙이기 실패: {detail[-1] if detail else exc}", file=sys.stderr)
        return False


def mux(video_path, audio_path, out_path):
    """Attach the sound bed and normalise loudness for Shorts playback."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error",
             "-i", str(video_path), "-i", str(audio_path),
             "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-af", "loudnorm=I=-14:TP=-1.0:LRA=11",
             "-shortest", str(out_path)],
            check=True, capture_output=True,
        )
        return True
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip().splitlines()
        print(f"  [warn] 오디오 결합 실패: {detail[-1] if detail else exc}", file=sys.stderr)
        return False
