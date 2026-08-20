#!/usr/bin/env python3
"""
YouTube에 제품 리뷰 영상 업로드 (Shorts + 장편)

특징:
- Shorts와 장편 동시 업로드
- 제휴 링크 자동 설명란 포함
- 클릭 추적 가능한 형식
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
COUPANG_AFFILIATE_ID = os.getenv("COUPANG_AFFILIATE_ID", "")


def get_youtube_client():
    """OAuth 인증"""
    if not YOUTUBE_REFRESH_TOKEN:
        print("❌ YOUTUBE_REFRESH_TOKEN 필요", file=sys.stderr)
        sys.exit(1)

    credentials = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
    )

    request = google.auth.transport.requests.Request()
    credentials.refresh(request)

    return build("youtube", "v3", credentials=credentials)


def build_description(
    product_name: str,
    price: int,
    rating: float,
    pros: list,
    cons: list,
    amazon_link: str,
    coupang_link: str,
) -> str:
    """
    영상 설명 생성 (제휴 링크 포함)
    """
    pros_text = "\n".join([f"✅ {pro}" for pro in pros[:3]])
    cons_text = "\n".join([f"❌ {con}" for con in cons[:2]])

    description = f"""{product_name}
⭐ {rating}/5.0 | 가격: {price:,}원

【장점】
{pros_text}

【단점】
{cons_text}

【구매링크】
🛒 쿠팡: {coupang_link}
"""

    if amazon_link:
        description += f"🛒 아마존: {amazon_link}\n"

    description += """
【공개】
이 영상에는 제휴 링크가 포함되어 있습니다.
링크를 통한 구매로 저희에게 작은 수수료가 지급되며,
이는 채널 운영에 도움이 됩니다. 감사합니다!

【매일 새로운 리뷰】
구독 + 알림 설정해서 최신 제품 리뷰를 받으세요!

---
AI 자동화로 생성된 제품 리뷰입니다."""

    return description


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list,
    privacy_status: str = "public",
    schedule_time: datetime = None,
) -> str:
    """
    YouTube에 단일 영상 업로드
    """
    youtube = get_youtube_client()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags[:50],
            "categoryId": "26",  # 제품 리뷰 (Howto & Style)
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    if schedule_time:
        body["status"]["publishAt"] = schedule_time.isoformat() + "Z"

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)

    print(f"📤 업로드: {title[:40]}...", file=sys.stderr)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  진행: {int(status.progress() * 100)}%", end="\r", file=sys.stderr)

    video_id = response["id"]
    print(f"✅ 완료: {video_id}                  ", file=sys.stderr)
    return video_id


def main():
    """메인 프로세스"""
    videos_json = sys.stdin.read()
    videos_data = json.loads(videos_json)

    videos = videos_data["videos"]
    uploaded = []
    now = datetime.now()

    for i, video in enumerate(videos):
        if not video.get("shorts_video"):
            print(f"⚠️ Shorts 파일 없음: {video['product_id']}")
            continue

        product_name = video["product_name"]
        rating = video["rating"]
        price = video.get("price", 0)
        pros = video.get("pros", [])
        cons = video.get("cons", [])
        coupang_link = video.get("coupang_link", "")
        amazon_link = video.get("amazon_link", "")
        shorts_path = video["shorts_video"]
        long_path = video.get("long_video")

        # 설명 생성
        description = build_description(
            product_name=product_name,
            price=price,
            rating=rating,
            pros=pros,
            cons=cons,
            amazon_link=amazon_link,
            coupang_link=coupang_link,
        )

        # 1. Shorts 업로드 (즉시 공개)
        shorts_title = f"[리뷰] {product_name}"
        shorts_id = upload_video(
            video_path=shorts_path,
            title=shorts_title,
            description=description,
            tags=["shorts", "review", "product", "쿠팡", "제품리뷰"],
            privacy_status="public",
            schedule_time=None,
        )

        uploaded.append(
            {
                "type": "shorts",
                "video_id": shorts_id,
                "title": shorts_title,
                "url": f"https://youtube.com/shorts/{shorts_id}",
                "published_at": now.isoformat(),
            }
        )

        # 2. 장편 업로드 (2시간 후 예약)
        if long_path and Path(long_path).exists():
            long_title = f"[상세리뷰] {product_name}"
            schedule_time = now + timedelta(hours=2)

            long_id = upload_video(
                video_path=long_path,
                title=long_title,
                description=description + "\n\n📱 Shorts 버전도 확인하세요!",
                tags=["review", "product", "쿠팡", "제품리뷰"],
                privacy_status="public",
                schedule_time=schedule_time,
            )

            uploaded.append(
                {
                    "type": "long",
                    "video_id": long_id,
                    "title": long_title,
                    "url": f"https://youtube.com/watch?v={long_id}",
                    "scheduled_at": schedule_time.isoformat(),
                }
            )

    result = {
        "date": videos_data["date"],
        "category": videos_data["category"],
        "total_uploaded": len(uploaded),
        "videos": uploaded,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
