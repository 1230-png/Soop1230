#!/usr/bin/env python3
"""Generate food shorts video with narration and Coupang links."""
import json
import sys
from pathlib import Path
import random
from datetime import datetime

# Add parent path for shared utilities
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared import common


def generate_food_video():
    """Generate a complete food shorts video with narration."""
    output_dir = Path(__file__).parent.parent / "output" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load food items
    food_list_path = Path(__file__).parent.parent / "data" / "food_list.json"
    with open(food_list_path, encoding='utf-8') as f:
        food_items = json.load(f)

    # Pick random food item
    food_item = random.choice(food_items)
    food_id = food_item["id"]
    title = food_item["title"]
    description = food_item["description"]
    tags = food_item.get("tags", [])

    video_id = f"food_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Paths
    bg_path = output_dir / f"{video_id}_bg.png"
    audio_path = output_dir / f"{video_id}_audio.mp3"
    video_path = output_dir / f"{video_id}.mp4"
    metadata_path = output_dir / f"{video_id}_metadata.json"

    print(f"Generating video for: {title}", file=sys.stderr)

    try:
        # 1. Generate background with title
        print("  → Creating background...", file=sys.stderr)
        palette = common.pick_palette(str(food_id))
        bg_img = common.make_background(palette[0], palette[1])

        # Draw title on background
        font_path = common.find_korean_font()
        from PIL import ImageFont, ImageDraw
        font = ImageFont.truetype(font_path, 80)
        draw = ImageDraw.Draw(bg_img)
        y = common.draw_centered(draw, title, font, 400, (255, 255, 255), wrap_width=10)

        bg_img.save(bg_path)

        # 2. Generate narration
        print("  → Creating narration...", file=sys.stderr)
        narration_text = f"{title}. {description.split(chr(10))[0]}"
        try:
            common.tts_save_segment('ko', narration_text, audio_path, use_elevenlabs_for_en=False)
        except Exception as e:
            # Fallback: Generate silence if TTS fails (network/local environment)
            print(f"  ⚠ TTS failed ({type(e).__name__}), using silence...", file=sys.stderr)
            common.generate_silence(3.0, audio_path)

        # 3. Mux video (image + audio)
        print("  → Muxing video...", file=sys.stderr)
        common.mux_video(bg_path, audio_path, video_path)

        # 4. Save metadata
        print("  → Saving metadata...", file=sys.stderr)
        metadata = {
            "video_id": video_id,
            "food_id": food_id,
            "title": title,
            "description": description,
            "tags": tags,
            "video_path": str(video_path),
            "metadata_path": str(metadata_path),
            "generated_at": datetime.now().isoformat()
        }

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        # 5. Update used_videos log
        log_path = Path(__file__).parent.parent / "data" / "used_videos.csv"
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().isoformat()},{video_id},{title},generated\n")

        print(f"✅ Generated: {video_id}", file=sys.stderr)

        # Output result as JSON (for GitHub Actions)
        result = {
            "video_id": video_id,
            "video_path": str(video_path),
            "metadata_path": str(metadata_path)
        }
        print(json.dumps(result, ensure_ascii=False))

        return video_id

    except Exception as e:
        print(f"❌ Error generating video: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    generate_food_video()
