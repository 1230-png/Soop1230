#!/usr/bin/env python3
"""Generate food shorts video."""
import json
import sys
from pathlib import Path
import random

# Add parent path for shared utilities
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared import common


def generate_food_video():
    """Generate a food shorts video."""
    output_dir = Path(__file__).parent.parent / "output" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get random food item
    food_list_path = Path(__file__).parent.parent / "data" / "food_list.json"
    with open(food_list_path) as f:
        food_items = json.load(f)

    food_item = random.choice(food_items)

    # Generate video (placeholder for now)
    video_id = f"video_{random.randint(10000, 99999)}"
    video_path = output_dir / f"{video_id}.mp4"

    # Create metadata
    metadata = {
        "video_id": video_id,
        "title": food_item["title"],
        "description": food_item.get("description", ""),
        "tags": food_item.get("tags", []),
        "video_path": str(video_path),
        "metadata_path": str(output_dir / f"{video_id}_metadata.json")
    }

    # Save metadata
    metadata_path = output_dir / f"{video_id}_metadata.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Create dummy video file (for testing)
    video_path.touch()

    # Output result as JSON (for GitHub Actions parsing)
    result = {
        "video_id": video_id,
        "video_path": str(video_path),
        "metadata_path": str(metadata_path)
    }

    print(json.dumps(result, ensure_ascii=False))
    return video_id


if __name__ == "__main__":
    generate_food_video()
