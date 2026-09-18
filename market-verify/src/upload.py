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

REQUIRED_ENV = (CLIENT_ID_ENV, CLIENT_SECRET_ENV, REFRESH_TOKEN_ENV)

# **공용 YT_* 로 떨어지지 않는다.** 채널마다 제 자격 증명과 제 구글 클라우드
# 프로젝트를 쓴다는 것이 이 저장소의 방침이다. 대체 경로를 열어 두면 MV_* 를
# 빠뜨렸을 때 조용히 남의 자격 증명으로 올라간다 — 틀린 채널에 올라간 영상은
# 사람이 손으로 지워야 하고, 할당량도 남의 것을 깎는다.
#
# 형제 채널(run_shorts.yml)이 YT_* 를 대체로 열어 둔 적이 있고, 그 주석에
# "하나를 여러 채널이 같이 쓰다가 업로드가 깨졌다"는 기록이 남아 있다.
# 없으면 없다고 말하고 멈추는 편이 낫다.


# market-verify 에는 발급 스크립트를 따로 두지 않는다. 형제 채널 것과 하는 일이
# 같고, 네 번째 사본이 생기면 한쪽만 고치는 일이 생긴다. 대신 어느 것을 어떻게
# 부르는지 여기 적어 둔다 — 없는 절차를 가리키는 에러만큼 사람을 헤매게 하는 것이 없다.
HOW_TO_GET = """  발급은 본인 PC 에서 한 번만 한다(브라우저 로그인이 필요해 CI 에서는 안 된다).
    pip install google-auth-oauthlib
    python3 channel_200y3b/scripts/get_refresh_token.py --client-secret-file client_secret.json
    윈도우 PowerShell 이면 python3 대신 python, 경로 구분자는 역슬래시.

  client_secret.json 은 **머니로직 전용 구글 클라우드 프로젝트**에서 받은 것을
  쓴다. 다른 채널 것을 돌려쓰지 않는다 — 그러면 할당량을 나눠 쓰게 되고(할당량은
  채널이 아니라 프로젝트 단위다), 어느 채널이 먼저 떨어질지 그날 순서에 달린다.
  프로젝트 만드는 절차는 channel_200y3b/SETUP.md 의 1~4 절과 같다
  (동의 화면을 '프로덕션'으로 올리지 않으면 토큰이 7일마다 만료된다).

  출력된 세 값을 저장소 Secrets 에 넣는다:
    MV_CLIENT_ID / MV_CLIENT_SECRET / MV_REFRESH_TOKEN
    MV_CHANNEL_ID — 머니로직 채널 ID(UC...). 넣어 두면 엉뚱한 채널로 올라가지 않는다."""


class UploadConfigError(RuntimeError):
    """자격 증명이 없거나 올릴 채널이 확인되지 않는다."""


def _env(name, env):
    return (env.get(name) or "").strip()


def check_credentials(env=None):
    """업로드 전에 자격 증명을 본다. 문제가 없으면 None."""
    env = os.environ if env is None else env
    missing = [name for name in REQUIRED_ENV if not _env(name, env)]
    if missing:
        return (
            f"업로드 자격 증명이 없다: {', '.join(missing)}.\n"
            "  이 채널 전용 값이어야 한다. 다른 채널 것을 넣으면 그 채널에 올라간다.\n"
            f"{HOW_TO_GET}"
        )
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
