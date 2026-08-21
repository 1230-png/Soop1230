"""Fetch free cooking footage and ASMR sound from open sources.

Everything here is free of charge. Two of the providers want a free API key
(registration only, no card, no paid tier needed); Wikimedia Commons needs
none at all and is always tried, so the pipeline still finds material on a
runner with no secrets configured.

  video   Pixabay -> Pexels -> Wikimedia Commons
  audio   Freesound -> Wikimedia Commons

Providers are tried in order and the first usable file wins. Downloads are
cached under assets/cache/ keyed by query, so a repeat run costs no requests
and stays inside every free tier.

Nothing here raises. A missing key, a rate limit, a dead host or a truncated
body all return None and let the caller decide — which for video means
failing the run rather than falling back to a still frame.
"""

import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TIMEOUT = 30
UA = "food-shorts/1.0 (https://github.com/1230-png/Soop1230)"

MIN_VIDEO_BYTES = 60_000
MIN_AUDIO_BYTES = 8_000

# Shorts are 9:16; a clip shorter than this cannot fill a scene without
# looping hard enough to look like a stutter.
MIN_CLIP_SECONDS = 2.0


def _cache(root: Path, kind: str, query: str, suffix: str) -> Path:
    folder = root / "cache" / kind
    folder.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(query.encode("utf-8")).hexdigest()[:16]
    return folder / f"{key}{suffix}"


def _get_json(url, headers=None):
    request = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _download(url, dest: Path, min_bytes: int):
    try:
        request = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = response.read()
    except Exception as exc:  # noqa: BLE001
        print(f"    [warn] 내려받기 실패: {type(exc).__name__}", file=sys.stderr)
        return None

    if len(data) < min_bytes:
        print(f"    [warn] 파일이 너무 작음 ({len(data)}B)", file=sys.stderr)
        return None

    dest.write_bytes(data)
    return dest


def _try(label, fn, *args):
    """Run one provider, swallowing its failures so the next can be tried."""
    try:
        return fn(*args)
    except urllib.error.HTTPError as exc:
        print(f"    [warn] {label} HTTP {exc.code}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"    [warn] {label} 실패: {type(exc).__name__}", file=sys.stderr)
    return None


# --------------------------------------------------------------------------
# video providers
# --------------------------------------------------------------------------


def _pixabay_video(query):
    key = os.environ.get("PIXABAY_API_KEY", "")
    if not key:
        return None
    base = os.environ.get("PIXABAY_API_BASE", "https://pixabay.com/api")
    url = f"{base}/videos/?" + urllib.parse.urlencode({
        "key": key, "q": query, "per_page": 20,
        "video_type": "film", "safesearch": "true",
    })
    hits = _get_json(url).get("hits") or []

    best = None
    for hit in hits:
        if float(hit.get("duration") or 0) < MIN_CLIP_SECONDS:
            continue
        streams = hit.get("videos") or {}
        for size in ("large", "medium", "small"):
            stream = streams.get(size) or {}
            if stream.get("url") and int(stream.get("height") or 0) >= 720:
                # Prefer the tallest available frame for a 9:16 crop.
                score = int(stream["height"]) / max(int(stream.get("width") or 1), 1)
                if best is None or score > best[0]:
                    best = (score, stream["url"])
                break
    return best[1] if best else None


def _pexels_video(query):
    key = os.environ.get("PEXELS_API_KEY", "")
    if not key:
        return None
    base = os.environ.get("PEXELS_API_BASE", "https://api.pexels.com/videos")
    url = f"{base}/search?" + urllib.parse.urlencode({
        "query": query, "per_page": 15, "orientation": "portrait",
    })
    videos = _get_json(url, {"Authorization": key}).get("videos") or []

    best = None
    for video in videos:
        if float(video.get("duration") or 0) < MIN_CLIP_SECONDS:
            continue
        for f in video.get("video_files") or []:
            h, w = int(f.get("height") or 0), int(f.get("width") or 1)
            if f.get("link") and h >= 720:
                score = h / max(w, 1)
                if best is None or score > best[0]:
                    best = (score, f["link"])
    return best[1] if best else None


def _commons_video(query):
    """Wikimedia Commons — no key, CC-licensed, always available."""
    base = os.environ.get("COMMONS_API_BASE", "https://commons.wikimedia.org/w/api.php")
    url = f"{base}?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:video {query}", "gsrlimit": 15,
        "gsrnamespace": 6, "prop": "imageinfo",
        "iiprop": "url|size|mime", "iiurlwidth": 1080,
    })
    pages = (_get_json(url).get("query") or {}).get("pages") or {}
    for page in pages.values():
        for info in page.get("imageinfo") or []:
            mime = info.get("mime", "")
            if info.get("url") and mime.startswith("video/"):
                return info["url"]
    return None


VIDEO_PROVIDERS = [
    ("Pixabay", _pixabay_video),
    ("Pexels", _pexels_video),
    ("Commons", _commons_video),
]


def fetch_video(query, assets_dir: Path):
    """A local path to real footage for `query`, or None."""
    query = (query or "").strip()
    if not query:
        return None

    cached = _cache(assets_dir, "video", query, ".mp4")
    if cached.exists() and cached.stat().st_size > MIN_VIDEO_BYTES:
        return cached

    for label, provider in VIDEO_PROVIDERS:
        url = _try(label, provider, query)
        if not url:
            continue
        got = _download(url, cached, MIN_VIDEO_BYTES)
        if got:
            print(f"    · {label}: {query}", file=sys.stderr)
            return got
    return None


# --------------------------------------------------------------------------
# audio providers
# --------------------------------------------------------------------------


def _freesound_audio(query):
    key = os.environ.get("FREESOUND_API_KEY", "")
    if not key:
        return None
    base = os.environ.get("FREESOUND_API_BASE", "https://freesound.org/apiv2")
    url = f"{base}/search/text/?" + urllib.parse.urlencode({
        "query": query, "page_size": 15,
        "filter": "duration:[2.0 TO 30.0]",
        "fields": "id,name,previews,duration",
        "token": key,
    })
    for result in _get_json(url).get("results") or []:
        previews = result.get("previews") or {}
        # The preview mp3s are what the free token grants; full-quality
        # downloads need OAuth and are not needed for a background bed.
        for quality in ("preview-hq-mp3", "preview-lq-mp3"):
            if previews.get(quality):
                return previews[quality]
    return None


def _commons_audio(query):
    base = os.environ.get("COMMONS_API_BASE", "https://commons.wikimedia.org/w/api.php")
    url = f"{base}?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:audio {query}", "gsrlimit": 15,
        "gsrnamespace": 6, "prop": "imageinfo", "iiprop": "url|mime",
    })
    pages = (_get_json(url).get("query") or {}).get("pages") or {}
    for page in pages.values():
        for info in page.get("imageinfo") or []:
            if info.get("url") and info.get("mime", "").startswith("audio/"):
                return info["url"]
    return None


AUDIO_PROVIDERS = [
    ("Freesound", _freesound_audio),
    ("Commons", _commons_audio),
]


def fetch_audio(query, assets_dir: Path):
    """A local path to a real recorded sound for `query`, or None."""
    query = (query or "").strip()
    if not query:
        return None

    cached = _cache(assets_dir, "audio", query, ".mp3")
    if cached.exists() and cached.stat().st_size > MIN_AUDIO_BYTES:
        return cached

    for label, provider in AUDIO_PROVIDERS:
        url = _try(label, provider, query)
        if not url:
            continue
        got = _download(url, cached, MIN_AUDIO_BYTES)
        if got:
            print(f"    · {label}: {query}", file=sys.stderr)
            return got
    return None


def configured():
    """Which optional free keys this run has, for the log line."""
    return [
        name for name, env in (
            ("Pixabay", "PIXABAY_API_KEY"),
            ("Pexels", "PEXELS_API_KEY"),
            ("Freesound", "FREESOUND_API_KEY"),
        ) if os.environ.get(env)
    ]
