#!/usr/bin/env python3
"""
YouTube에 뉴스 영상 업로드 (Shorts + 롱폼)

특징:
- Shorts와 롱폼 동시 업로드
- 자동 예약 공개
- 원본 링크 자동 포함
- 카테고리별 맞춤 설명
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


def get_youtube_client():
    """OAuth 인증"""
    if not YOUTUBE_REFRESH_TOKEN:
        print("❌ YOUTUBE_REFRESH_TOKEN 환경변수 필요", file=sys.stderr)
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


def build_description(title_ko: str, category: str, original_url: str, hashtags: list) -> str:
    """
    설명 텍스트 생성
    """
    category_names = {
        "ai": "AI & 머신러닝 뉴스",
        "crypto": "암호화폐 & 블록체인 뉴스",
        "startup": "스타트업 & VC 뉴스",
        "tech": "기술 뉴스",
    }

    description = f"""{title_ko}

📰 {category_names.get(category, "기술 뉴스")}

원본 기사: {original_url}

태그: {" ".join(hashtags)}

---
AI 자동화로 생성된 뉴스 요약입니다.
최신 뉴스를 매일 받으세요: 구독 + 알림 설정

구독 이유:
✅ 매일 최신 뉴스 (아침/저녁)
✅ 30초 Shorts (빠른 업데이트)
✅ 3분 상세분석 (깊이 있는 이해)
✅ 신뢰할 수 있는 출처 기반"""

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
    한 개 영상 업로드
    """
    youtube = get_youtube_client()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags[:50],
            "categoryId": "25",  # 뉴스 & 정치
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

    print(f"📤 업로드: {title[:40]}...")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  진행: {int(status.progress() * 100)}%", end="\r")

    video_id = response["id"]
    print(f"✅ 완료: {video_id}                  ")
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
            print(f"⚠️ Shorts 파일 없음: {video['summary_id']}")
            continue

        title_ko = video["title_ko"]
        category = video["category"]
        hashtags = video["hashtags"]
        original_url = video["original_url"]
        shorts_path = video["shorts_video"]
        long_path = video.get("long_video")

        # 1. Shorts 업로드 (즉시)
        description = build_description(title_ko, category, original_url, hashtags)

        shorts_title = f"[{category.upper()}] {title_ko}"
        shorts_id = upload_video(
            video_path=shorts_path,
            title=shorts_title,
            description=description,
            tags=hashtags + ["shorts", "news", category],
            privacy_status="public",
            schedule_time=None,  # 즉시 공개
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

        # 2. 롱폼 업로드 (있으면, 6시간 후 예약)
        if long_path and Path(long_path).exists():
            long_title = f"[분석] {title_ko}"
            schedule_time = now + timedelta(hours=6)

            long_id = upload_video(
                video_path=long_path,
                title=long_title,
                description=description + "\n\n📺 Shorts 버전도 확인하세요!",
                tags=hashtags + ["analysis", "news", category],
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
