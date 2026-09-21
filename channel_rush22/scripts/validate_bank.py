"""Check content_bank.json before a run tries to publish from it.

Cheap insurance against the failure modes that are invisible until a scheduled
run breaks or, worse, publishes something malformed: a duplicate id silently
skips an entry, a missing field crashes mid-render after the upload quota has
already been spent, and text that is too long produces a video YouTube will not
treat as a Short.

    python scripts/validate_bank.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT_BANK = ROOT / "scripts" / "content_bank.json"

REQUIRED = ["id", "topic", "hook", "body", "punch", "tags"]

# edge-tts at the channel's +12% rate reads Korean at roughly 5.5 characters
# per second. Scene pauses add ~1.6s in total. Measured against rendered
# output, this estimate runs slightly conservative, which is the right
# direction for a limit check.
CHARS_PER_SEC = 5.5
SCENE_PAUSES = 1.6
SHORTS_LIMIT = 60
# Flag well before the hard limit — the estimate is not exact and a video that
# lands at 59s leaves no room for a slower voice.
WARN_AT = 50


def estimate_seconds(item) -> float:
    spoken = sum(len(item[f]) for f in ("hook", "body", "punch"))
    return spoken / CHARS_PER_SEC + SCENE_PAUSES


def main() -> int:
    bank = json.loads(CONTENT_BANK.read_text(encoding="utf-8"))
    errors, warnings = [], []

    seen = {}
    for index, item in enumerate(bank):
        label = item.get("id", f"index {index}")

        missing = [f for f in REQUIRED if not item.get(f)]
        if missing:
            errors.append(f"{label}: missing or empty field(s): {', '.join(missing)}")
            continue

        if item["id"] in seen:
            errors.append(
                f"{item['id']}: duplicate id (also at index {seen[item['id']]}). "
                "A duplicate is treated as already used and silently skipped."
            )
        seen[item["id"]] = index

        if not isinstance(item["tags"], list) or not item["tags"]:
            errors.append(f"{label}: tags must be a non-empty list")

        seconds = estimate_seconds(item)
        if seconds > SHORTS_LIMIT:
            errors.append(
                f"{label}: ~{seconds:.0f}s exceeds the {SHORTS_LIMIT}s Shorts limit"
            )
        elif seconds > WARN_AT:
            warnings.append(f"{label}: ~{seconds:.0f}s is close to the limit")

        if len(item["hook"]) > 92:  # leaves room for the " #shorts" title suffix
            warnings.append(f"{label}: hook will be truncated in the video title")

    for warning in warnings:
        print(f"⚠️  {warning}")
    for error in errors:
        print(f"❌ {error}", file=sys.stderr)

    if errors:
        print(f"\n{len(errors)} problem(s) in {CONTENT_BANK.name}.", file=sys.stderr)
        return 1

    longest = max(bank, key=estimate_seconds)
    print(
        f"✅ {len(bank)} entries valid "
        f"(longest: {longest['id']} at ~{estimate_seconds(longest):.0f}s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
