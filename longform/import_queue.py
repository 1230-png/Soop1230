"""Convert the Shorts phrase queue into longform/data/phrases.json.

    python3 longform/import_queue.py [--source PATH ...] [--out PATH]

Reads the Shorts data but never writes to it — the long-form pipeline keeps
its own copy so the two can drift without either breaking the other.

Key names are matched loosely (JSON, JSONL and CSV all work) because the
Shorts side has used more than one field naming over time.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCES = [
    ROOT.parent / "channel_200y3b" / "scripts" / "phrase_bank.json",
]
DEFAULT_OUT = ROOT / "data" / "phrases.json"

# First match wins, so the most specific spelling is listed first.
FIELDS = {
    "en": ["en", "phrase_en", "english", "phrase", "expression", "sentence"],
    "ko": ["ko", "meaning_ko", "korean", "meaning", "translation"],
    "ex_en": ["ex_en", "example_en", "example"],
    "ex_ko": ["ex_ko", "example_ko"],
    "topic": ["topic", "category", "tag"],
    "id": ["id", "phrase_id"],
}


def pick(row: dict, names) -> str:
    for n in names:
        v = row.get(n)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def read_source(path: Path) -> list:
    if not path.exists():
        print(f"[import] skip (not found): {path}", file=sys.stderr)
        return []

    text = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()

    if suffix == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    elif suffix == ".json":
        data = json.loads(text)
        # Tolerate both a bare list and a wrapper like {"phrases": [...]}.
        if isinstance(data, dict):
            for key in ("phrases", "items", "queue", "data"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
            else:
                data = list(data.values())
        rows = [r for r in data if isinstance(r, dict)]
    elif suffix in (".csv", ".tsv"):
        delim = "\t" if suffix == ".tsv" else ","
        rows = list(csv.DictReader(text.splitlines(), delimiter=delim))
    else:
        print(f"[import] skip (unsupported type): {path}", file=sys.stderr)
        return []

    print(f"[import] {path.name}: {len(rows)} rows", file=sys.stderr)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", action="append", type=Path)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    sources = args.source or DEFAULT_SOURCES
    seen, out_rows, skipped = set(), [], 0

    for src in sources:
        for row in read_source(Path(src)):
            en = pick(row, FIELDS["en"])
            ko = pick(row, FIELDS["ko"])
            if not en or not ko:
                skipped += 1
                continue
            key = " ".join(en.lower().split())
            if key in seen:
                skipped += 1
                continue
            seen.add(key)
            out_rows.append({
                "id": pick(row, FIELDS["id"]) or f"P{len(out_rows) + 1:04d}",
                "en": en,
                "ko": ko,
                "ex_en": pick(row, FIELDS["ex_en"]),
                "ex_ko": pick(row, FIELDS["ex_ko"]),
                "topic": pick(row, FIELDS["topic"]),
            })

    if not out_rows:
        raise SystemExit("No usable rows found — check --source paths.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out_rows, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    topics = sorted({r["topic"] for r in out_rows if r["topic"]})
    print(f"[import] wrote {len(out_rows)} phrases to {args.out} "
          f"({skipped} skipped, {len(topics)} topics)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
