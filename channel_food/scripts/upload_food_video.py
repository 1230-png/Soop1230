"""Upload food content Shorts to YouTube with Coupang partner links.

Reads YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN from environment.
Automatically inserts Coupang partner links into video description based on
matched products from coupang_products.json.
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

SCOPES = ["https://www.googleapis.com/auth/youtube"]


def get_credentials() -> Credentials:
    client_id = os.environ.get("FOOD_CLIENT_ID") or os.environ.get("YT_CLIENT_ID")
    client_secret = os.environ.get("FOOD_CLIENT_SECRET") or os.environ.get("YT_CLIENT_SECRET")
    refresh_token = os.environ.get("FOOD_REFRESH_TOKEN") or os.environ.get("YT_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise EnvironmentError(
            "Missing YouTube credentials: set FOOD_CLIENT_ID, FOOD_CLIENT_SECRET, FOOD_REFRESH_TOKEN "
            "or YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN"
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def enhance_description_with_coupang(metadata: dict) -> str:
    """메타데이터에서 쿠팡 상품 링크를 설명에 추가"""
    description = metadata.get("description", "")

    products = metadata.get("coupang_products", [])
    if products:
        description += "\n\n" + "=" * 50
        description += "\n📱 쿠팡 추천 상품 (파트너스 링크)\n"
        description += "=" * 50 + "\n"

        for product in products[:5]:
            name = product.get("name", "상품명")
            link = product.get("link", "")
            if link:
                description += f"• [{name}]({link})\n"

        description += "\n쿠팡 파트너스 활동으로 일정의 수수료를 받을 수 있습니다.\n"

    return description


def upload(video_path: str, metadata_path: str, privacy_status: str, log_file: Path) -> str:
    """유튜브에 영상 업로드"""
    video_file = Path(video_path)
    meta_file = Path(metadata_path)

    if not video_file.exists():
        raise FileNotFoundError(f"Video file not found: {video_file}")
    if not meta_file.exists():
        raise FileNotFoundError(f"Metadata file not found: {meta_file}")

    with open(meta_file, encoding="utf-8") as f:
        metadata = json.load(f)

    description = enhance_description_with_coupang(metadata)

    youtube = build("youtube", "v3", credentials=get_credentials())

    body = {
        "snippet": {
            "title": metadata["title"],
            "description": description,
            "tags": metadata.get("tags", []),
            "categoryId": metadata.get("category_id", "26"),
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": metadata.get("make_for_kids", False),
        },
    }

    media = MediaFileUpload(
        str(video_file),
        chunksize=-1,
        resumable=True,
        mimetype="video/mp4",
    )
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()

    youtube_video_id = response["id"]
    print(f"✅ 업로드 완료: https://youtube.com/watch?v={youtube_video_id}")

    if log_file and log_file.exists():
        update_log(str(video_file), youtube_video_id, "uploaded", log_file)

    return youtube_video_id


def update_log(video_path: str, youtube_video_id: str, status: str, log_file: Path) -> None:
    """업로드 기록 업데이트"""
    if not log_file.exists():
        return

    with open(log_file, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        if not rows:
            return
        fieldnames = list(rows[0].keys())

    video_name = Path(video_path).name
    for row in rows:
        if row.get("video_path", "").endswith(video_name):
            row["youtube_video_id"] = youtube_video_id
            row["status"] = status
            break

    with open(log_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="음식 쇼츠를 유튜브에 업로드 (쿠팡 링크 자동 추가)"
    )
    parser.add_argument(
        "--video-path",
        required=True,
        help="영상 파일 경로 (예: channel_food/output/food_shorts_1.mp4)",
    )
    parser.add_argument(
        "--metadata-path",
        required=True,
        help="메타데이터 JSON 경로 (예: channel_food/output/metadata_1.json)",
    )
    parser.add_argument(
        "--privacy-status",
        default="unlisted",
        choices=["public", "unlisted", "private"],
        help="유튜브 공개 설정",
    )
    parser.add_argument(
        "--log-file",
        default="used_log.csv",
        help="업로드 기록을 저장할 CSV 파일",
    )
    args = parser.parse_args()

    youtube_video_id = upload(
        args.video_path,
        args.metadata_path,
        args.privacy_status,
        ROOT / args.log_file,
    )

    return youtube_video_id


if __name__ == "__main__":
    video_id = main()
    sys.exit(0 if video_id else 1)
