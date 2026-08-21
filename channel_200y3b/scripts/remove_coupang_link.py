"""One-off cleanup: strip the broken Coupang affiliate line from the
description of every already-uploaded video, using video IDs recorded in
used_log.csv / used_log_longform.csv.

Run locally:
    python remove_coupang_link.py
"""

import csv
import re
import sys
from pathlib import Path

from upload_video import get_youtube_client

ROOT = Path(__file__).resolve().parent.parent
LOG_FILES = [ROOT / "used_log.csv", ROOT / "used_log_longform.csv"]

# Matches the trailing "\n\n📚 추천 상품: <url>" block appended by upload_video.py
COUPANG_LINE_RE = re.compile(r"\n\n📚 추천 상품:.*$", re.DOTALL)


def collect_video_ids() -> list[str]:
    ids = []
    for log_file in LOG_FILES:
        if not log_file.exists():
            continue
        with open(log_file, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                vid = row.get("youtube_video_id", "").strip()
                if vid:
                    ids.append(vid)
    return ids


def main():
    video_ids = collect_video_ids()
    if not video_ids:
        print("No video IDs found in log files.")
        return

    youtube = get_youtube_client()
    cleaned = 0
    skipped = 0

    for video_id in video_ids:
        resp = youtube.videos().list(part="snippet", id=video_id).execute()
        items = resp.get("items", [])
        if not items:
            print(f"⚠️  {video_id}: not found (skipped)")
            skipped += 1
            continue

        snippet = items[0]["snippet"]
        old_desc = snippet["description"]
        new_desc = COUPANG_LINE_RE.sub("", old_desc)

        if new_desc == old_desc:
            print(f"— {video_id}: no Coupang line found (skipped)")
            skipped += 1
            continue

        snippet["description"] = new_desc
        youtube.videos().update(part="snippet", body={"id": video_id, "snippet": snippet}).execute()
        print(f"✅ {video_id}: cleaned")
        cleaned += 1

    print(f"\nDone. Cleaned {cleaned}, skipped {skipped}.")


if __name__ == "__main__":
    sys.exit(main())
