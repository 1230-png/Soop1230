#!/usr/bin/env python3
"""
비디오를 YouTube 자동 업로드

흐름:
1. OAuth 토큰으로 YouTube API 인증
2. 비디오 + 썸네일 + 메타데이터 업로드
3. 스케줄 공개 또는 즉시 공개
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# YouTube API 권한 (업로드 필요)
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# 환경변수에서 토큰 읽기
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")


def get_youtube_client():
    """OAuth 인증으로 YouTube API 클라이언트 생성"""

    if not YOUTUBE_REFRESH_TOKEN:
        print("❌ YOUTUBE_REFRESH_TOKEN 환경변수 필요", file=sys.stderr)
        print("   MOBILE_API_TOKEN_GUIDE.md 참고", file=sys.stderr)
        sys.exit(1)

    # Refresh token으로 새 access token 생성
    # (실제 구현은 client_id/secret이 필요하지만,
    #  GitHub Actions Secrets에서 직접 전달 가정)

    credentials = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("YOUTUBE_CLIENT_ID", ""),
        client_secret=os.getenv("YOUTUBE_CLIENT_SECRET", ""),
    )

    # 토큰 갱신
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)

    return build("youtube", "v3", credentials=credentials)


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list,
    thumbnail_path: str = None,
    schedule_time: str = None,
) -> str:
    """
    YouTube에 비디오 업로드

    Args:
        video_path: 비디오 파일 경로
        title: 영상 제목
        description: 설명
        tags: 태그 리스트
        thumbnail_path: 썸네일 이미지 경로
        schedule_time: 공개 시간 (ISO 8601, 미지정 시 즉시 공개)

    Returns:
        video_id
    """

    youtube = get_youtube_client()

    # 메타데이터 구성
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags[:50],  # 최대 50개
            "categoryId": "22",  # 영상/영화 카테고리
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            "privacyStatus": "private",  # 기본 공개 안함
        },
    }

    # 예약 공개 설정
    if schedule_time:
        body["status"]["privacyStatus"] = "public"
        body["status"]["publishAt"] = schedule_time
    else:
        body["status"]["privacyStatus"] = "public"  # 즉시 공개

    # 비디오 파일 업로드
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)

    print(f"📤 업로드 시작: {title}")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  업로드 진행: {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"✅ 업로드 완료: {video_id}")

    # 썸네일 업로드
    if thumbnail_path and Path(thumbnail_path).exists():
        try:
            with open(thumbnail_path, "rb") as f:
                youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumbnail_path)).execute()
            print(f"✅ 썸네일 업로드: {video_id}")
        except Exception as e:
            print(f"⚠️ 썸네일 업로드 실패: {e}")

    return video_id


def create_thumbnail(title: str, image_path: str, output_path: str):
    """
    원본 이미지에 제목 텍스트를 오버레이한 썸네일 생성
    YouTube 썸네일 권장: 1280x720px
    """
    from PIL import Image, ImageDraw, ImageFont

    try:
        # 배경 이미지 로드 및 크기 조정
        img = Image.open(image_path).convert("RGB")
        img.thumbnail((1280, 720), Image.Resampling.LANCZOS)

        # 새 1280x720 캔버스 생성 및 이미지 중앙 배치
        thumbnail = Image.new("RGB", (1280, 720), color=(0, 0, 0))
        offset = ((thumbnail.width - img.width) // 2, (thumbnail.height - img.height) // 2)
        thumbnail.paste(img, offset)

        # 텍스트 오버레이
        draw = ImageDraw.Draw(thumbnail)

        # 글꼴 선택 (한글 폰트, 미설치 시 기본)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", size=60)
        except:
            font = ImageFont.load_default()

        # 텍스트 중앙 정렬
        text = title[:30]  # 최대 30글자
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (thumbnail.width - text_width) // 2
        text_y = 600

        # 텍스트 테두리 (가독성)
        for adj_x in [-3, -1, 1, 3]:
            for adj_y in [-3, -1, 1, 3]:
                draw.text((text_x + adj_x, text_y + adj_y), text, font=font, fill=(0, 0, 0))

        # 흰 텍스트
        draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255))

        thumbnail.save(output_path, quality=95)
        print(f"✅ 썸네일 생성: {output_path}")

    except Exception as e:
        print(f"⚠️ 썸네일 생성 실패: {e}")


def main():
    """메인 프로세스"""
    # 표준입력에서 영상 정보 JSON 받기
    video_json = sys.stdin.read()
    video_info = json.loads(video_json)

    video_path = video_info["video_path"]
    title = video_info["title"]
    description = video_info["description"]
    tags = video_info.get("tags", ["감성", "이야기", "짧은영상"])

    # 썸네일 생성
    bg_image = Path(__file__).parent.parent / "assets" / f"{video_info['video_id']}_bg.jpg"
    thumbnail_path = Path(__file__).parent.parent / "output" / f"{video_info['video_id']}_thumb.jpg"

    if bg_image.exists():
        create_thumbnail(title, str(bg_image), str(thumbnail_path))

    # 예약 공개 (매일 12:00 KST)
    now = datetime.now()
    next_publish = (now + timedelta(days=1)).replace(hour=12, minute=0, second=0)

    # YouTube에 업로드
    video_id = upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        thumbnail_path=str(thumbnail_path),
        schedule_time=next_publish.isoformat() + "Z",
    )

    # 결과 출력
    result = {
        "video_id": video_id,
        "title": title,
        "url": f"https://youtube.com/watch?v={video_id}",
        "scheduled_at": next_publish.isoformat(),
    }

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
