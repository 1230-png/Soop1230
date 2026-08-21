#!/usr/bin/env python3
"""
YouTube Shorts 일괄 자동 업로드

특징:
- 여러 영상 한 번에 업로드
- 이중언어 (한국어/영어)
- 자동 예약 공개
- 제휴 링크 자동 삽입
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
    """OAuth 인증으로 YouTube API 클라이언트 생성"""

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


def upload_short(
    video_path: str,
    title: str,
    description: str,
    tags: list,
    schedule_time: datetime = None,
) -> str:
    """
    한 개의 Shorts 업로드

    Args:
        video_path: 비디오 파일 경로
        title: 영상 제목 (이중언어)
        description: 설명
        tags: 태그 리스트
        schedule_time: 공개 시간

    Returns:
        video_id
    """

    youtube = get_youtube_client()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags[:50],
            "categoryId": "22",  # 영상/영화
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    # 예약 공개
    if schedule_time:
        body["status"]["publishAt"] = schedule_time.isoformat() + "Z"

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)

    print(f"📤 업로드: {title[:30]}...")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            percent = int(status.progress() * 100)
            print(f"  진행: {percent}%", end="\r")

    video_id = response["id"]
    print(f"✅ 완료: {video_id}                  ")

    return video_id


def build_description(title_en: str, category: str, hashtags: list) -> str:
    """
    설명 텍스트 생성
    - 영어 제목
    - 카테고리
    - 해시태그
    - 제휴 링크 (나중에 추가 가능)
    """

    description = f"""{title_en}

Category: {category}

💡 Daily growth tips for your success
매일 성장하는 당신을 응원합니다

Tags: {" ".join(hashtags)}

---
Shorts created with AI automation
More tips daily: Subscribe & Enable notifications
매일 새로운 팁을 알려드립니다: 구독 + 알림 설정"""

    return description


def calculate_schedule_times(num_videos: int) -> list:
    """
    여러 영상의 공개 시간 자동 계산
    하루 중 10개를 균등 배분
    """
    now = datetime.now()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)

    # 08:00 ~ 22:00 사이에 배분 (14시간)
    times = []
    for i in range(num_videos):
        # 8시부터 22시까지 균등 배분
        hour = 8 + int((i / num_videos) * 14)
        times.append(tomorrow.replace(hour=hour, minute=0, second=0))

    return times


def main():
    """메인 프로세스: 여러 Shorts 일괄 업로드"""

    videos_json = sys.stdin.read()
    videos_data = json.loads(videos_json)

    videos = videos_data["videos"]
    schedule_times = calculate_schedule_times(len(videos))

    uploaded = []

    for i, video in enumerate(videos):
        video_path = video["video_path"]
        title_ko = video["title_ko"]
        title_en = video["title_en"]
        hashtags = video["hashtags"]
        category = video["category"]

        if not Path(video_path).exists():
            print(f"⚠️ 파일 없음: {video_path}")
            continue

        # 제목: 한국어 + 영어
        title = f"{title_ko} | {title_en}"

        # 설명 생성
        description = build_description(title_en, category, hashtags)

        # 업로드
        schedule_time = schedule_times[i]
        video_id = upload_short(
            video_path=video_path,
            title=title,
            description=description,
            tags=hashtags + ["shorts", "growth", "tips", "motivation"],
            schedule_time=schedule_time,
        )

        uploaded.append(
            {
                "video_id": video_id,
                "title": title,
                "url": f"https://youtube.com/shorts/{video_id}",
                "scheduled_at": schedule_time.isoformat(),
            }
        )

    # 결과 출력
    result = {
        "date": videos_data["date"],
        "total_uploaded": len(uploaded),
        "videos": uploaded,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
