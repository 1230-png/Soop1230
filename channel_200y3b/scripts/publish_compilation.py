"""Generate and publish weekly long-form compilation.

End-to-end pipeline:
1. Generate compilation video (generate_compilation.py)
2. Upload to YouTube with custom thumbnail (upload_video.py)
3. Update logs
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
OUTPUT_DIR = ROOT / "output"


def run_command(cmd, description):
    """Run command and handle errors."""
    print(f"\n▶ {description}...", file=sys.stderr)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=SCRIPTS_DIR)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:\n{e.stderr}", file=sys.stderr)
        raise


def main():
    try:
        # Step 1: Generate compilation
        output_id = run_command(
            ["python3", "generate_compilation.py"],
            "Generating long-form compilation"
        )

        if not output_id:
            raise SystemExit("Failed to generate compilation (no output_id)")

        print(f"Generated compilation: {output_id}", file=sys.stderr)

        # Step 2: Load metadata
        meta_path = OUTPUT_DIR / f"{output_id}.json"
        if not meta_path.exists():
            raise SystemExit(f"Metadata not found: {meta_path}")

        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        video_path = OUTPUT_DIR / f"{output_id}.mp4"
        thumbnail_path = OUTPUT_DIR / f"{output_id}_thumb.png"

        if not video_path.exists():
            raise SystemExit(f"Video file not found: {video_path}")

        # Step 3: Upload to YouTube with custom thumbnail
        upload_cmd = [
            "python3", "upload_video.py",
            str(video_path),
            "--title", metadata["title"],
            "--description", metadata["description"],
            "--log-file", str(ROOT / "used_log_longform.csv"),
        ]

        if thumbnail_path.exists():
            upload_cmd.extend(["--thumbnail", str(thumbnail_path)])

        youtube_video_id = run_command(upload_cmd, "Uploading to YouTube")

        if youtube_video_id:
            print(f"\n✨ Published: {metadata['title']}", file=sys.stderr)
            print(f"YouTube: https://youtube.com/watch?v={youtube_video_id}", file=sys.stderr)
            return 0
        else:
            raise SystemExit("Upload succeeded but no YouTube video ID returned")

    except Exception as e:
        print(f"\n❌ Publishing failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
