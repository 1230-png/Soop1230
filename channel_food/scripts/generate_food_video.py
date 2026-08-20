"""Generate a food content Shorts: recipe / review / product demo,
narrated with natural neural voices and muxed into a vertical mp4.

Free stack: Pillow (image/text), edge-tts (neural TTS), ffmpeg (mux).
"""

import asyncio
import csv
import datetime
import json
import os
import random
import ssl
import sys
from pathlib import Path

from PIL import ImageDraw, ImageFont
import aiohttp
import edge_tts

import common

os.environ.setdefault("SSL_CERT_FILE", "/root/.ccr/ca-bundle.crt")
os.environ.setdefault("REQUESTS_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")

ROOT = Path(__file__).resolve().parent.parent
FOOD_BANK = ROOT / "scripts" / "food_content.json"
COUPANG_PRODUCTS = ROOT / "scripts" / "coupang_products.json"
USED_LOG = ROOT / "used_log.csv"
OUTPUT_DIR = ROOT / "output"

OUTPUT_DIR.mkdir(exist_ok=True)


def load_food_content():
    with open(FOOD_BANK, "r", encoding="utf-8") as f:
        return json.load(f)


def load_coupang_products():
    with open(COUPANG_PRODUCTS, "r", encoding="utf-8") as f:
        return json.load(f)


def get_used_ids():
    if not USED_LOG.exists():
        return set()
    used = set()
    try:
        with open(USED_LOG, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                for row in reader:
                    if row.get("content_id"):
                        used.add(int(row["content_id"]))
    except:
        pass
    return used


def pick_unused_content():
    content = load_food_content()
    used = get_used_ids()
    available = [c for c in content if c["id"] not in used]

    if not available:
        print("[warn] 모든 콘텐츠를 사용했습니다. 리셋 후 다시 시작합니다.", file=sys.stderr)
        return random.choice(content)

    return random.choice(available)


def match_coupang_products(content):
    """콘텐츠의 keywords와 쿠팡 상품을 매칭"""
    products_db = load_coupang_products()
    matched = []

    for keyword in content.get("coupang_keywords", []):
        for category, products in products_db.get("categories", {}).items():
            for product in products:
                if keyword.lower() in str(product.get("keywords", [])).lower():
                    matched.append(product)
                    break
        if len(matched) >= 2:
            break

    if not matched and products_db.get("default_products"):
        matched = products_db["default_products"][:2]

    return matched


def make_title_image(content):
    """타이틀 이미지 생성"""
    top_color, bottom_color = common.pick_palette(str(content["id"]))
    img = common.make_background(top_color, bottom_color)
    draw = ImageDraw.Draw(img)

    font_path = common.find_korean_font()
    title_font = ImageFont.truetype(font_path, 80)
    subtitle_font = ImageFont.truetype(font_path, 50)

    y = 400
    y = common.draw_centered(
        draw,
        content["title"],
        title_font,
        y,
        fill=(255, 255, 255),
        wrap_width=15,
        line_gap=20,
    )

    y = 1200
    common.draw_centered(
        draw,
        content.get("korean", ""),
        subtitle_font,
        y,
        fill=(200, 220, 255),
        wrap_width=20,
        line_gap=15,
    )

    return img


def make_product_image(content, products):
    """쿠팡 상품 추천 이미지"""
    top_color, bottom_color = common.pick_palette(str(content["id"]) + "prod")
    img = common.make_background(bottom_color, top_color)
    draw = ImageDraw.Draw(img)

    font_path = common.find_korean_font()
    title_font = ImageFont.truetype(font_path, 60)
    product_font = ImageFont.truetype(font_path, 50)

    y = 300
    draw.text((60, y), "💰 추천 상품", font=title_font, fill=(255, 215, 0))

    y = 550
    for i, product in enumerate(products[:3]):
        text = f"• {product['name']}"
        draw.text((100, y), text, font=product_font, fill=(255, 255, 255))
        y += 120

    y = 1650
    draw.text((60, y), "쿠팡에서 확인", font=title_font, fill=(255, 100, 100))

    return img


async def generate_narration(content):
    """음성 나레이션 생성"""
    narrations = {}

    title_ko = f"{content.get('korean', content['title'])}입니다."
    desc_ko = content.get("description", "")

    audio_files = []

    title_path = OUTPUT_DIR / f"title_{content['id']}.mp3"
    await common.tts_save(title_ko, common.KO_VOICE, title_path)
    audio_files.append((title_path, 2))

    if desc_ko:
        desc_path = OUTPUT_DIR / f"desc_{content['id']}.mp3"
        await common.tts_save(desc_ko, common.KO_VOICE, desc_path)
        audio_files.append((desc_path, 3))

    end_path = OUTPUT_DIR / f"end_{content['id']}.mp3"
    end_text = "구독과 좋아요 부탁드립니다!"
    await common.tts_save(end_text, common.KO_VOICE, end_path)
    audio_files.append((end_path, 2))

    return audio_files


async def make_video(content, audio_files, products):
    """ffmpeg로 최종 영상 생성 (이미지 + 음성)"""
    import subprocess

    title_img = make_title_image(content)
    product_img = make_product_image(content, products)

    title_img_path = OUTPUT_DIR / f"title_{content['id']}.png"
    product_img_path = OUTPUT_DIR / f"product_{content['id']}.png"
    title_img.save(title_img_path)
    product_img.save(product_img_path)

    audio_generated = await generate_narration_to_files(content, audio_files)

    video_path = OUTPUT_DIR / f"food_shorts_{content['id']}.mp4"
    video_no_audio_path = OUTPUT_DIR / f"food_shorts_{content['id']}_noaudio.mp4"
    audio_concat_path = OUTPUT_DIR / f"audio_{content['id']}.mp3"

    concat_list = OUTPUT_DIR / "concat.txt"
    with open(concat_list, "w") as f:
        for img_path, duration in [
            (title_img_path, 3),
            (product_img_path, 4),
        ]:
            f.write(f"file '{img_path}'\n")
            f.write(f"duration {duration}\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1080:1920",
        "-c:v", "libx264",
        "-crf", "23",
        str(video_no_audio_path),
    ]

    subprocess.run(cmd, check=True, capture_output=True)

    if audio_generated:
        title_audio = OUTPUT_DIR / f"title_{content['id']}.mp3"
        end_audio = OUTPUT_DIR / f"end_{content['id']}.mp3"
        desc_audio = OUTPUT_DIR / f"desc_{content['id']}.mp3"

        audio_files_to_concat = [title_audio, end_audio]
        if desc_audio.exists():
            audio_files_to_concat.insert(1, desc_audio)

        if all(p.exists() for p in audio_files_to_concat):
            audio_concat_list = OUTPUT_DIR / "audio_concat.txt"
            with open(audio_concat_list, "w") as f:
                for audio_path in audio_files_to_concat:
                    f.write(f"file '{audio_path}'\n")

            subprocess.run([
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(audio_concat_list),
                "-c", "copy",
                str(audio_concat_path),
            ], check=True, capture_output=True)

            subprocess.run([
                "ffmpeg", "-y",
                "-i", str(video_no_audio_path),
                "-i", str(audio_concat_path),
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                str(video_path),
            ], check=True, capture_output=True)

            video_no_audio_path.unlink(missing_ok=True)
            audio_concat_list.unlink(missing_ok=True)
            audio_concat_path.unlink(missing_ok=True)
        else:
            video_path = video_no_audio_path
    else:
        video_path = video_no_audio_path

    concat_list.unlink(missing_ok=True)
    return video_path


async def generate_narration_to_files(content, audio_files):
    """음성 파일 생성 (ElevenLabs 또는 edge-tts 사용)"""
    title_ko = f"{content.get('korean', content['title'])}입니다."
    desc_ko = content.get("description", "")
    end_text = "구독과 좋아요 부탁드립니다!"

    try:
        title_path = OUTPUT_DIR / f"title_{content['id']}.mp3"
        comm = edge_tts.Communicate(title_ko, common.KO_VOICE)
        await comm.save(str(title_path))

        if desc_ko:
            desc_path = OUTPUT_DIR / f"desc_{content['id']}.mp3"
            comm = edge_tts.Communicate(desc_ko, common.KO_VOICE)
            await comm.save(str(desc_path))

        end_path = OUTPUT_DIR / f"end_{content['id']}.mp3"
        comm = edge_tts.Communicate(end_text, common.KO_VOICE)
        await comm.save(str(end_path))

        print(f"  ✓ 음성 생성 완료", file=sys.stderr)
        return True
    except Exception as e:
        print(f"  ⚠️  음성 생성 건너뜀: {str(e)[:80]}", file=sys.stderr)
        return False


def log_usage(content, video_path, products):
    """사용 기록 저장"""
    if not USED_LOG.exists():
        with open(USED_LOG, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "date",
                    "content_id",
                    "type",
                    "title",
                    "video_path",
                    "products",
                ],
            )
            writer.writeheader()

    product_names = ", ".join([p.get("name", "") for p in products])

    with open(USED_LOG, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "content_id",
                "type",
                "title",
                "video_path",
                "products",
            ],
        )
        writer.writerow({
            "date": datetime.datetime.now().isoformat(),
            "content_id": content["id"],
            "type": content["type"],
            "title": content["title"],
            "video_path": str(video_path),
            "products": product_names,
        })


def make_metadata(content, video_path, products):
    """업로드용 메타데이터 JSON"""
    matched_products = match_coupang_products(content)
    if not matched_products:
        matched_products = products

    hashtags = " ".join(content.get("hashtags", ["#음식", "#요리"]))

    product_links = "\n".join([
        f"🛒 {p.get('name', '')}: {p.get('link', '')}"
        for p in matched_products[:3]
    ])

    description = f"""{content.get('description', '')}

{product_links}

━━━━━━━━━━━━━━━━━━━━
📺 오늘뭐먹지? (@오늘뭐먹지-f2d)
맛있게 먹는 일상 영상 채널
구독 👉 https://youtube.com/@오늘뭐먹지-f2d
━━━━━━━━━━━━━━━━━━━━

#음식 #요리 #쿠팡 #추천 {hashtags}
"""

    metadata = {
        "title": content["title"],
        "description": description,
        "tags": content.get("hashtags", []),
        "privacy_status": "public",
        "category_id": "26",
        "make_for_kids": False,
        "coupang_products": matched_products,
    }

    return metadata


async def main():
    content = pick_unused_content()
    products = match_coupang_products(content)

    print(f"[생성] {content['type']}: {content['title']}", file=sys.stderr)
    print(f"[상품] {len(products)}개 매칭됨", file=sys.stderr)

    video_path = await make_video(content, [], products)
    print(f"[완료] {video_path}", file=sys.stderr)

    metadata = make_metadata(content, video_path, products)
    metadata_path = OUTPUT_DIR / f"metadata_{content['id']}.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    log_usage(content, video_path, products)

    return {
        "video_path": str(video_path),
        "metadata_path": str(metadata_path),
        "content_id": content["id"],
    }


if __name__ == "__main__":
    import asyncio
    result = asyncio.run(main())
    print(json.dumps(result, ensure_ascii=False))
