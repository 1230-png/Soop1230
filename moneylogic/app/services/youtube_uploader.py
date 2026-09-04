"""YouTube Data API를 이용한 영상 업로드.

비공개(private) 모드로 업로드한다.
"""

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# YouTube API 범위
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_youtube_client():
    """YouTube API 클라이언트 생성."""
    # 환경 변수에서 인증 정보 읽기
    creds_json = os.getenv("YOUTUBE_CREDENTIALS_JSON")
    token_json = os.getenv("YOUTUBE_TOKEN_JSON")

    if not creds_json:
        raise ValueError("YOUTUBE_CREDENTIALS_JSON 환경 변수가 필요합니다.")

    # 기존 토큰 로드
    creds = None
    if token_json and Path(token_json).exists():
        creds = Credentials.from_authorized_user_file(token_json, SCOPES)

    # 토큰 갱신 필요
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    # 토큰이 없으면 새로 인증
    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file(
            creds_json,
            SCOPES,
            redirect_uri="http://localhost:8888",
        )
        creds = flow.run_local_server(port=0)

        # 토큰 저장
        if token_json:
            Path(token_json).parent.mkdir(parents=True, exist_ok=True)
            with open(token_json, "w") as f:
                f.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


async def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list = None,
    category_id: str = "27",  # Education
    is_private: bool = True,
) -> str:
    """YouTube에 영상을 업로드한다.

    Args:
        video_path: 로컬 MP4 파일 경로
        title: 영상 제목
        description: 설명
        tags: 태그 리스트
        category_id: YouTube 카테고리 ID (27=Education)
        is_private: True면 비공개, False면 공개

    Returns:
        YouTube 비디오 ID
    """
    if not video_path.exists():
        raise FileNotFoundError(f"영상 파일을 찾을 수 없습니다: {video_path}")

    # YouTube 클라이언트 생성
    youtube = get_youtube_client()

    # 영상 메타데이터
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": category_id,
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            "privacyStatus": "private" if is_private else "public",
            "embeddable": True,
            "madeForKids": False,
        },
    }

    # 미디어 파일 업로드
    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10MB chunks
    )

    print(f"📤 YouTube 업로드 중: {title}")
    print(f"   파일: {video_path.name} ({video_path.stat().st_size / (1024**2):.1f} MB)")

    # 업로드 요청
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    # 업로드 실행 (진행 표시)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            print(f"   진행률: {progress}%")

    video_id = response["id"]
    print(f"✅ 업로드 완료!")
    print(f"   비디오 ID: {video_id}")
    print(f"   링크: https://www.youtube.com/watch?v={video_id}")

    return video_id
