"""Cooking ASMR beds for the food Shorts.

Recorded clips in assets/sounds/ are always preferred, but the channel has
to keep publishing before that folder is filled, and a silent Shorts is
dead on arrival. So every cooking sound here can also be synthesized from
filtered noise with ffmpeg — 지글지글 sizzle, 보글보글 boil, 칼질 chop,
소스 뿌리기 pour, 김 모락모락 steam — which needs no assets at all.

Each profile returns an ffmpeg filter-graph fragment fed by one noise
source; build_bed() mixes the profiles a step calls for into a single bed.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

SAMPLE_RATE = 44100

# Every profile is (noise colour, filter chain). The chains are tuned so the
# layers sit in different frequency bands and stay distinguishable when
# amix() sums them: sizzle up top, chop in the mids, boil underneath.
SOUND_PROFILES = {
    # 기름 튀는 지글지글 — bright, fast, dense crackle
    "기름": ("white", "highpass=f=1900,lowpass=f=9000,tremolo=f=17:d=0.55,volume=0.42"),
    # 고기 굽는 소리 — same family, a little heavier
    "고기": ("white", "highpass=f=1400,lowpass=f=7000,tremolo=f=13:d=0.5,volume=0.40"),
    # 국물 보글보글 — slow, round, low bubbling
    "국물": ("brown", "lowpass=f=900,tremolo=f=3.4:d=0.85,volume=0.55"),
    # 불 위 끓는 소리 — broader than 국물, with a rolling boil on top
    "불": ("brown", "lowpass=f=1500,tremolo=f=5.5:d=0.7,volume=0.48"),
    # 칼질 — sparse, percussive mid-band taps
    "채소": ("pink", "bandpass=f=1100:w=1400,tremolo=f=2.2:d=0.95,volume=0.5"),
    # 계란 깨고 푸는 소리 — short broadband transients
    "계란": ("white", "bandpass=f=2400:w=2600,tremolo=f=1.6:d=0.92,volume=0.38"),
    # 소스 뿌리기 — a narrow, wet stream
    "소스": ("pink", "bandpass=f=1500:w=900,tremolo=f=9:d=0.35,volume=0.34"),
    # 김 모락모락 — the quiet hiss that sits under everything else
    "김": ("white", "highpass=f=3800,volume=0.16"),
}

# Steam is always present in a hot dish, so it underpins every bed and gives
# the mix a continuous floor instead of gaps between the rhythmic layers.
BASE_LAYER = "김"


def available_profiles():
    return sorted(SOUND_PROFILES)


def parse_sound_types(raw):
    """'기름,불' -> ['기름', '불'], dropping anything we have no profile for."""
    if not raw:
        return []
    parts = [p.strip() for p in str(raw).replace("|", ",").split(",")]
    return [p for p in parts if p in SOUND_PROFILES]


def _layer_args(index, colour, duration, seed):
    # Without a per-bed seed every video would render byte-identical sizzle
    # for the same cue, and a recipe that sizzles in two consecutive steps
    # would repeat the exact same audio — which reads as a stuck loop.
    # md5 rather than hash(): str hashing is salted per process, so hash()
    # would give a different bed on every run and nothing would reproduce.
    digest = hashlib.md5(str(seed).encode("utf-8")).hexdigest()
    noise_seed = (int(digest[:8], 16) + index * 137) % 100000
    return [
        "-f", "lavfi",
        "-i", f"anoisesrc=d={duration:.2f}:c={colour}:r={SAMPLE_RATE}:a=0.9:s={noise_seed}",
    ]


def synthesize_bed(
    sound_types, duration, out_path, fade=0.35, fade_in=True, fade_out=True, seed=""
):
    """Mix one synthesized layer per sound type into a single mp3 bed.

    fade_in/fade_out are off for beds that will be joined with acrossfade —
    the crossfade already shapes those edges, and fading twice dips the
    sound to nothing at every scene change.

    Returns True on success. Falls back to the caller's silence handling if
    ffmpeg refuses the graph for any reason.
    """
    layers = list(dict.fromkeys(parse_sound_types(sound_types)))
    if BASE_LAYER not in layers:
        layers.append(BASE_LAYER)

    cmd = ["ffmpeg", "-y", "-v", "error"]
    for i, name in enumerate(layers):
        colour, _chain = SOUND_PROFILES[name]
        cmd += _layer_args(i, colour, duration, f"{seed}:{name}")

    parts = []
    for i, name in enumerate(layers):
        _colour, chain = SOUND_PROFILES[name]
        parts.append(f"[{i}:a]{chain}[a{i}]")

    mixed = "".join(f"[a{i}]" for i in range(len(layers)))
    # amix normalises by input count, which would bury the bed as layers are
    # added; scale back up and let the per-layer volumes keep the sum in range.
    tail = [
        f"amix=inputs={len(layers)}:duration=longest:dropout_transition=0",
        f"volume={len(layers) * 0.8:.2f}",
    ]
    if fade_in:
        tail.append(f"afade=t=in:st=0:d={fade}")
    if fade_out:
        tail.append(f"afade=t=out:st={max(0.0, duration - fade):.2f}:d={fade}")
    parts.append(f"{mixed}{','.join(tail)}[out]")

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[out]",
        "-t", f"{duration:.2f}",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_path),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip().splitlines()
        print(f"  [warn] ASMR 합성 실패: {detail[-1] if detail else exc}", file=sys.stderr)
        return False


def concat_beds(bed_paths, out_path, crossfade=0.0):
    """Join per-step beds so each scene keeps its own sound.

    crossfade MUST match the video's xfade duration. The video loses
    `crossfade` seconds per transition because consecutive scenes overlap,
    so beds joined end to end would run that much longer and slide out of
    sync — by the last step of a 4-scene Shorts the sizzle would be playing
    a full transition behind the step that calls for it. acrossfade overlaps
    the beds by exactly the same amount, keeping both timelines identical.
    """
    beds = [Path(p) for p in bed_paths]
    if not beds:
        return False

    if len(beds) == 1:
        return _run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(beds[0]),
             "-c:a", "libmp3lame", "-b:a", "192k", str(out_path)],
            "사운드 변환",
        )

    if crossfade <= 0:
        listing = Path(out_path).parent / f"{Path(out_path).stem}_beds.txt"
        listing.write_text(
            "\n".join(f"file '{p.resolve()}'" for p in beds), encoding="utf-8"
        )
        try:
            return _run(
                ["ffmpeg", "-y", "-v", "error",
                 "-f", "concat", "-safe", "0", "-i", str(listing),
                 "-c:a", "libmp3lame", "-b:a", "192k", str(out_path)],
                "사운드 이어붙이기",
            )
        finally:
            listing.unlink(missing_ok=True)

    cmd = ["ffmpeg", "-y", "-v", "error"]
    for bed in beds:
        cmd += ["-i", str(bed)]

    steps, prev = [], "[0:a]"
    for i in range(1, len(beds)):
        label = "[out]" if i == len(beds) - 1 else f"[m{i}]"
        steps.append(
            f"{prev}[{i}:a]acrossfade=d={crossfade}:c1=tri:c2=tri{label}"
        )
        prev = label

    cmd += [
        "-filter_complex", ";".join(steps),
        "-map", "[out]",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_path),
    ]
    return _run(cmd, "사운드 교차 페이드")


def _run(cmd, label):
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip().splitlines()
        print(f"  [warn] {label} 실패: {detail[-1] if detail else exc}", file=sys.stderr)
        return False
