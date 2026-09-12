"""edge-tts wrapper: one sentence in, one cached mp3 out.

edge-tts is free and needs no API key, but it talks to an unofficial
Microsoft endpoint that fails a single call now and then even when hundreds
of others in the same run succeed — so every call is retried, and every
result is cached by content hash. A 70-minute pack re-run after a crash
then costs almost nothing.

--offline swaps synthesis for silence sized from the text length. It keeps
the whole pipeline (timing, cards, concat, encode) testable with no network,
which is the only way to debug a build without burning runner minutes.
"""

import hashlib
import subprocess
import time
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "tts_cache"

# Rough speaking pace used only by --offline, to give silence a plausible
# length so timings and chapter marks stay in a believable range.
OFFLINE_CHARS_PER_SECOND = 14.0
OFFLINE_MIN_SECONDS = 0.8


class TTSError(RuntimeError):
    pass


def _key(text: str, voice: str, rate: str) -> str:
    return hashlib.sha1(f"{text}|{voice}|{rate}".encode("utf-8")).hexdigest()


def duration_of(path: Path) -> float:
    """Length of an audio file in seconds, via ffprobe."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def make_silence(seconds: float, out_path: Path) -> Path:
    """Generate a silent mp3 of the given length."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", f"{seconds:.3f}", "-q:a", "9", str(out_path)],
        check=True, capture_output=True,
    )
    return out_path


def synthesize(text: str, voice: str, rate: str = "+0%", *,
               offline: bool = False, attempts: int = 3) -> Path:
    """Return the path to an mp3 of `text` spoken by `voice`.

    Results are cached, so calling this twice with the same arguments costs
    one ffprobe at most.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_key(text, voice, rate)}.mp3"
    if path.exists() and path.stat().st_size > 0:
        return path

    if offline:
        seconds = max(OFFLINE_MIN_SECONDS, len(text) / OFFLINE_CHARS_PER_SECOND)
        return make_silence(seconds, path)

    last = None
    for attempt in range(1, attempts + 1):
        try:
            subprocess.run(
                ["edge-tts", "--voice", voice, "--rate", rate,
                 "--text", text, "--write-media", str(path)],
                check=True, capture_output=True,
            )
            if path.exists() and path.stat().st_size > 0:
                return path
            last = TTSError("edge-tts wrote an empty file")
        except subprocess.CalledProcessError as e:
            last = e
        # A failed attempt can leave a truncated file behind; a later cache
        # hit on it would be silently wrong, so clear it before retrying.
        path.unlink(missing_ok=True)
        if attempt < attempts:
            time.sleep(2 * attempt)

    raise TTSError(f"edge-tts failed after {attempts} attempts for {text!r}: {last}")
