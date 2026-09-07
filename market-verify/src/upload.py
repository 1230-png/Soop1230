"""유튜브 업로드. 기본값은 비공개다.

공개 전환은 사람이 유튜브 스튜디오에서 직접 한다. 대본에 운영자 코멘트를
채웠는지, 화면이 의도대로 나왔는지 눈으로 보고 나서 할 일이다.
"""

import os
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube"]
CATEGORY_PEOPLE_AND_BLOGS = "22"
PRIVACY_CHOICES = ["private", "unlisted", "public"]

CLIENT_ID_ENV = "MV_CLIENT_ID"
CLIENT_SECRET_ENV = "MV_CLIENT_SECRET"
REFRESH_TOKEN_ENV = "MV_REFRESH_TOKEN"
CHANNEL_ID_ENV = "MV_CHANNEL_ID"

# 형제 채널이 이미 쓰는 이름. 전용 값이 없으면 이쪽으로 떨어진다.
FALLBACK_ENV = {
    CLIENT_ID_ENV: "YT_CLIENT_ID",
    CLIENT_SECRET_ENV: "YT_CLIENT_SECRET",
    REFRESH_TOKEN_ENV: "YT_REFRESH_TOKEN",
}


class UploadConfigError(RuntimeError):
    """자격 증명이 없거나 올릴 채널이 확인되지 않는다."""


def _env(name, env):
    value = env.get(name) or env.get(FALLBACK_ENV.get(name, ""), "")
    return value.strip()


def check_credentials(env=None):
    """업로드 전에 자격 증명을 본다. 문제가 없으면 None."""
    env = os.environ if env is None else env
    missing = [
        name
        for name in (CLIENT_ID_ENV, CLIENT_SECRET_ENV, REFRESH_TOKEN_ENV)
        if not _env(name, env)
    ]
    if missing:
        pairs = ", ".join(f"{n}(또는 {FALLBACK_ENV[n]})" for n in missing)
        return f"업로드 자격 증명이 없다: {pairs}. get_refresh_token 절차로 발급할 것."
    return None


def build_client(env=None):
    env = os.environ if env is None else env
    problem = check_credentials(env)
    if problem:
        raise UploadConfigError(problem)

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=_env(REFRESH_TOKEN_ENV, env),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=_env(CLIENT_ID_ENV, env),
        client_secret=_env(CLIENT_SECRET_ENV, env),
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def assert_target_channel(youtube, expected_channel_id):
    """엉뚱한 채널에 올리는 사고를 막는다.

    이 저장소는 채널 여러 개를 한곳에서 운영한다. 토큰을 잘못 넣으면
    다른 채널에 올라가고, 되돌리려면 사람이 손으로 지워야 한다.
    """
    if not expected_channel_id:
        return None
    response = youtube.channels().list(part="id", mine=True).execute()
    actual = [item["id"] for item in response.get("items", [])]
    if expected_channel_id not in actual:
        raise UploadConfigError(
            f"토큰이 가리키는 채널({actual})이 지정한 채널"
            f"({expected_channel_id})과 다르다. 업로드하지 않는다."
        )
    return expected_channel_id


def build_body(title, description, tags, privacy):
    if privacy not in PRIVACY_CHOICES:
        raise ValueError(f"privacy 는 {PRIVACY_CHOICES} 중 하나여야 한다: {privacy}")
    return {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:20],
            "categoryId": CATEGORY_PEOPLE_AND_BLOGS,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }


def upload(video_path, title, description, tags=(), privacy="private",
           thumbnail_path=None, env=None, client=None):
    """영상을 올리고 video id 를 돌려준다. 기본은 비공개."""
    from googleapiclient.http import MediaFileUpload

    env = os.environ if env is None else env
    youtube = build_client(env) if client is None else client
    assert_target_channel(youtube, _env(CHANNEL_ID_ENV, env))

    body = build_body(title, description, list(tags), privacy)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(video_path), chunksize=-1, resumable=True),
    )
    response = request.execute()
    video_id = response["id"]

    if thumbnail_path and Path(thumbnail_path).exists():
        youtube.thumbnails().set(
            videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))
        ).execute()
    return video_id
