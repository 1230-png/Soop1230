"""Generate and upload a channel banner for @200-y3b (매일 영어 한마디).

Draws a 2560x1440 banner in the channel's navy/teal brand palette with the
channel name centered in YouTube's safe area, then uploads it via
channelBanners().insert() and sets it as the channel's banner image.

Requires a refresh token with the broader 'youtube' scope — see SETUP.md.
"""

import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image, ImageDraw, ImageFont

import common

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

SCOPES = ["https://www.googleapis.com/auth/youtube"]

# YouTube banner canvas; the ~1546x423 centered region is the "safe area"
# shown on every device, so all text must fit inside it.
BANNER_WIDTH, BANNER_HEIGHT = 2560, 1440
SAFE_WIDTH, SAFE_HEIGHT = 1546, 423


def get_credentials() -> Credentials:
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def make_banner(font_path: str) -> Path:
    top_color, bottom_color = common.PALETTES[0]
    img = Image.new("RGB", (BANNER_WIDTH, BANNER_HEIGHT), top_color)
    draw = ImageDraw.Draw(img)
    for y in range(BANNER_HEIGHT):
        t = y / BANNER_HEIGHT
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        draw.line([(0, y), (BANNER_WIDTH, y)], fill=(r, g, b))

    safe_top = (BANNER_HEIGHT - SAFE_HEIGHT) // 2
    title_font = ImageFont.truetype(font_path, 92)
    sub_font = ImageFont.truetype(font_path, 42)

    title = "매일 영어 한마디"
    sub = "실생활 영어 표현을 매일 하나씩 · @200-y3b"

    bbox = draw.textbbox((0, 0), title, font=title_font)
    tx = (BANNER_WIDTH - (bbox[2] - bbox[0])) / 2
    ty = safe_top + (SAFE_HEIGHT * 0.32)
    draw.text((tx, ty), title, font=title_font, fill=(255, 255, 255))

    bbox = draw.textbbox((0, 0), sub, font=sub_font)
    sx = (BANNER_WIDTH - (bbox[2] - bbox[0])) / 2
    sy = ty + 130
    draw.text((sx, sy), sub, font=sub_font, fill=(200, 230, 225))

    out_path = OUTPUT_DIR / "channel_banner.png"
    img.save(out_path)
    return out_path


def main() -> int:
    OUTPUT_DIR.mkdir(exist_ok=True)
    font_path = common.find_korean_font()
    banner_path = make_banner(font_path)

    youtube = build("youtube", "v3", credentials=get_credentials())

    resp = youtube.channels().list(part="brandingSettings", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        print("No channel found for this account.", file=sys.stderr)
        return 1
    channel = items[0]
    channel_id = channel["id"]
    branding = channel.get("brandingSettings", {})

    upload = youtube.channelBanners().insert(
        media_body=MediaFileUpload(str(banner_path), mimetype="image/png")
    ).execute()
    banner_url = upload["url"]

    branding.setdefault("image", {})["bannerExternalUrl"] = banner_url
    youtube.channels().update(
        part="brandingSettings",
        body={"id": channel_id, "brandingSettings": branding},
    ).execute()

    print(f"Banner uploaded and set for channel {channel_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
