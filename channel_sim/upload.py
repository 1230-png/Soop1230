"""만들어 둔 한 편을 유튜브에 올린다.

    python3 channel_sim/upload.py --dir channel_sim/build/2026-09-21-E01

`channel_jp/upload.py` 계보를 그대로 잇는다. 앞 채널들에서 한 번씩 데인
네 가지를 지킨다.

1. **대체 자격 증명이 없다.** `longform/upload.py:40` 은 `Y3B_*` 가 없으면
   공용 `YT_*` 로 넘어간다. 여기는 `SIM_*` 뿐이고, 없으면 멈춘다. 남의
   자격 증명으로 올라가느니 멈추는 편이 낫다.
2. **채널 ID 를 코드에 박지 않는다.** `SIM_CHANNEL_ID` 가 없으면 자격 증명이
   실제로 가진 채널 ID 를 찍어 주고 멈춘다. 짐작해서 올리지 않는다.
3. **올리기 직전에 다시 검사한다.** build.py 가 이미 봤지만 그것은 다른
   실행이다. 특히 `--preview` 로 만든 폴더를 가리키는 사고가 쉽다 —
   꼭지마다 3초씩인 1분짜리가 그대로 올라간다.
4. **두 번 올리지 않는다.** metadata 에 영상 ID 가 이미 있으면 멈춘다.
"""

import argparse
import csv
import datetime
import json
import os
import sys
import time
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build as build_service
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build as builder  # noqa: E402

# 새로고침 요청에 스코프를 실어 보내지 않는다.
#
# google-auth 는 Credentials(scopes=...) 가 설정돼 있으면 그 값을 토큰 요청에
# 그대로 넣고, 구글은 발급 때보다 넓은 스코프를 invalid_scope 로 거절한다.
# 스코프는 코드가 아니라 토큰에 붙어 있다. None 이면 스코프를 보내지 않으므로
# 토큰이 실제로 가진 권한 그대로 새로고침된다.
SCOPES = None

# 이 채널 전용 접두사. 채널마다 제 구글 클라우드 프로젝트를 쓴다 — 유튜브
# 일일 할당량이 채널이 아니라 **프로젝트 단위**라, 돌려쓰면 서로의 몫을 깎는다.
PREFIX = "SIM"
CREDENTIAL_NAMES = ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN")
CHANNEL_ID_ENV = f"{PREFIX}_CHANNEL_ID"

# 잠깐 뒤 다시 해 보면 되는 응답들. 거절이 아니라 전파 지연이다.
RETRY_STATUSES = {409, 500, 502, 503}


def credentials(env) -> dict:
    """`SIM_*` 세 개. 하나라도 없으면 멈춘다.

    **대체 경로를 두지 않는다.** 공용 `YT_*` 로 넘어가게 해 두면 이 채널의
    시크릿을 깜빡한 날 남의 채널 자격 증명으로 조용히 올라간다. 유튜브의
    일일 할당량도 채널이 아니라 구글 클라우드 프로젝트 단위라, 돌려쓰면
    서로의 몫을 깎는다.
    """
    values, missing = {}, []
    for name in CREDENTIAL_NAMES:
        value = (env.get(f"{PREFIX}_{name}") or "").strip()
        if value:
            values[name] = value
        else:
            missing.append(f"{PREFIX}_{name}")
    if missing:
        raise SystemExit(
            "자격 증명이 없다: " + ", ".join(missing) + "\n"
            "이 채널 전용 값이다. 공용 YT_* 로 돌아가지 않는다 — 남의 "
            "채널로 올라가느니 멈춘다.")
    return values


def youtube_client(env):
    """인증하고, 올릴 채널이 맞는지 확인한다."""
    values = credentials(env)
    creds = Credentials(
        token=None,
        refresh_token=values["REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=values["CLIENT_ID"],
        client_secret=values["CLIENT_SECRET"],
        scopes=SCOPES)
    try:
        creds.refresh(Request())
    except RefreshError as error:
        # 그냥 두면 google-auth 의 스택 트레이스가 그대로 나온다. 토큰이
        # 만료되거나 취소된 날 워크플로 로그에서 보게 되는 것이 그것인데,
        # 무엇을 해야 하는지가 거기 없다.
        raise SystemExit(
            f"{PREFIX}_* 자격 증명(「돌려 보는 알고리즘」)으로 인증하지 못했다: "
            f"{error}\n"
            "대개 둘 중 하나다 — 리프레시 토큰이 취소됐거나(구글 계정 →\n"
            "보안 → 서드파티 앱), CLIENT_ID/SECRET 이 그 토큰을 발급한\n"
            "구글 클라우드 프로젝트의 것이 아니다. 토큰을 다시 발급할 것."
        ) from error

    youtube = build_service("youtube", "v3", credentials=creds)

    response = youtube.channels().list(part="id,snippet", mine=True).execute()
    items = response.get("items", [])
    if not items:
        raise SystemExit("이 자격 증명이 어느 채널 것인지 알 수 없다.")

    actual = items[0]["id"]
    title = items[0]["snippet"].get("title", "?")
    expected = (env.get(CHANNEL_ID_ENV) or "").strip()

    if not expected:
        # 채널 ID 를 코드에 박아 두지 않는다. 짐작해서 올리는 대신, 넣어야 할
        # 값을 찍어 주고 멈춘다. 엉뚱한 채널에 올라간 영상은 조용하고, 되돌리기
        # 번거롭다.
        raise SystemExit(
            f"{CHANNEL_ID_ENV} 가 없다. 이 자격 증명이 가진 채널은:\n"
            f"  {actual}  ({title})\n"
            f"맞으면 이 값을 {CHANNEL_ID_ENV} 시크릿에 넣고 다시 돌릴 것.")

    if actual != expected:
        raise SystemExit(
            f"올리지 않는다: 자격 증명은 {actual} ({title}) 의 것인데 "
            f"{CHANNEL_ID_ENV} 는 {expected} 이다.")

    print(f"[upload] 채널 확인: {title} ({actual})", file=sys.stderr)
    return youtube


def verify_before_upload(meta: dict) -> None:
    """build.py 와 같은 검사를 올리기 직전에 한 번 더.

    검사 규칙을 여기 베껴 두지 않고 build 쪽 함수를 부른다 — 두 벌이 되면
    한쪽만 고쳐진 채로 조용히 갈라진다.
    """
    builder.verify_publishable(meta)


def assert_not_uploaded(meta: dict, again: bool) -> None:
    """이미 올린 폴더인가.

    머니로직은 같은 제목의 영상이 여러 번 올라갔다. 중복 방지를 제목이 아니라
    날짜로 걸어 둔 탓이라, 하루에 두 번 돌면 그냥 두 편이 됐다. 여기서는
    올린 영상 ID 를 metadata 에 적고, 그 값이 있으면 멈춘다. 커리큘럼이
    정해져 있어 같은 편을 두 번 올리면 시리즈 번호가 어긋난다.
    """
    existing = (meta.get("youtube_video_id") or "").strip()
    if existing and not again:
        raise SystemExit(
            f"이 폴더는 이미 올렸다: "
            f"https://www.youtube.com/watch?v={existing}\n"
            "정말 한 편 더 올리려면 --again 을 줄 것.")


# 발행 기록. 어느 영상이 몇 편이었나를 잇는 유일한 자료다. 조회수는
# channel_health 의 metrics.csv 에 쌓이지만, 거기에는 영상 ID 밖에 없어
# 「시즌 1과 시즌 2 중 뭐가 먹히나」에 답할 방법이 없다. 그 연결을 여기서 만든다.
#
# append-only 다. 덮어쓰면 "지금 몇 편"만 남고 "얼마나 늘고 있나"가 사라진다.
# **이미 쌓인 파일에 칸을 늘리지 말 것** — 예전 줄과 칸 수가 달라지면
# DictReader 가 통째로 어긋난다.
PUBLISHED_PATH = Path(__file__).resolve().parent / "data" / "published.csv"
PUBLISHED_FIELDS = ("published_at", "episode", "size", "video_id",
                    "duration_seconds", "scene_count", "privacy", "title")


def published_row(meta: dict, video_id: str, privacy: str, now: str) -> dict:
    """발행 기록 한 줄. 전부 문자열로 둔다 — csv 가 어차피 그렇게 읽는다."""
    return {
        "published_at": now,
        "episode": meta.get("episode", ""),
        "size": str(meta.get("size", "")),
        "video_id": video_id,
        "duration_seconds": str(meta.get("duration_seconds", "")),
        "scene_count": str(len(meta.get("algorithms", []))),
        "privacy": privacy,
        "title": meta.get("title", ""),
    }


def append_published(row: dict, path: Path = None) -> None:
    """한 줄 덧붙인다. 처음이면 머리글부터.

    csv 모듈로 쓴다 — 제목에 쉼표가 들어가고, 손으로 이어 붙이면 그 줄부터
    칸이 밀린다. channel_200y3b 에서 실제로 그렇게 어긋난 적이 있다.
    """
    path = PUBLISHED_PATH if path is None else path
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists() or path.stat().st_size == 0
    with open(path, "a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PUBLISHED_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def chosen_privacy(meta: dict, privacy: str = "") -> str:
    """실제로 나가는 공개 설정.

    metadata 의 값이 기본이다. build.py 가 private 으로 적어 둔다 — 사람이
    한 번 보고 공개하라는 뜻이고, 그 기본값을 코드가 조용히 뒤집지 않는다.
    뒤집으려면 부르는 쪽이 값을 **적어서** 줘야 한다(워크플로의 privacy 입력).
    """
    return privacy or meta.get("privacyStatus", "private")


def video_body(meta: dict, privacy: str = "") -> dict:
    """videos().insert 에 넣을 본문.

    언어를 `ko` 로 적는다. 화면에 말은 없지만 제목과 설명이 한국어라,
    한국어 시청자에게 추천되어야 한다.
    """
    return {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta.get("tags", []),
            "categoryId": meta.get("categoryId", "28"),
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            "privacyStatus": chosen_privacy(meta, privacy),
            "madeForKids": False,
        },
    }


def upload(youtube, video_path: Path, meta: dict, privacy: str = "") -> str:
    # 재개 가능 업로드. 40분짜리는 한 번에 보내다 연결이 끊기면 빌드를 통째로
    # 다시 해야 할 만큼 크다.
    media = MediaFileUpload(str(video_path), mimetype="video/mp4",
                            chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status", body=video_body(meta, privacy), media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[upload] {int(status.progress() * 100)}%", file=sys.stderr)
    return response["id"]


def get_or_create_playlist(youtube, title: str) -> str:
    """이 제목의 재생목록 ID. 없으면 만든다."""
    page_token = None
    while True:
        response = youtube.playlists().list(
            part="id,snippet", mine=True, maxResults=50,
            pageToken=page_token).execute()
        for item in response.get("items", []):
            if item["snippet"]["title"] == title:
                return item["id"]
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    response = youtube.playlists().insert(
        part="snippet,status",
        body={"snippet": {"title": title},
              "status": {"privacyStatus": "public"}}).execute()
    print(f"[upload] 재생목록 {title!r} 를 만들었다", file=sys.stderr)
    return response["id"]


def add_to_playlist(youtube, video_id: str, title: str,
                    attempts: int = 4) -> None:
    """이 영상을 제 시리즈에 잇는다.

    한 편을 끝까지 본 사람이 떠나는 대신 다음 편으로 자동 재생된다. 이
    스크립트가 하는 일 중 시청 시간에 가장 크게 기여하는 부분이다.

    방금 만든 재생목록은 다음 호출에서 아직 안 보일 수 있다. 영어판에서
    첫 상황별 팩이 재생목록을 만든 직후 409 SERVICE_UNAVAILABLE 을 받았다.
    거절이 아니라 전파 지연이라 기다릴 값이 있고, 팩이 처음 발행될 때마다
    다시 생긴다.
    """
    try:
        playlist_id = get_or_create_playlist(youtube, title)
    except HttpError as error:
        print(f"[upload] 재생목록 {title!r} 를 찾지 못했다 (무시): {error}",
              file=sys.stderr)
        return

    for attempt in range(1, attempts + 1):
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={"snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video",
                                   "videoId": video_id},
                }}).execute()
            print(f"[upload] {video_id} 를 재생목록 {title!r} 에 넣었다",
                  file=sys.stderr)
            return
        except HttpError as error:
            if error.resp.status not in RETRY_STATUSES or attempt == attempts:
                # 영상은 이미 올라갔다. 재생목록 한 줄 때문에 실행을 실패로
                # 만들 값은 없다.
                print(f"[upload] 재생목록 실패 (무시): {error}", file=sys.stderr)
                return
            wait = 5 * attempt
            print(f"[upload] 재생목록에서 {error.resp.status} — {wait}초 뒤 "
                  f"다시 ({attempt}/{attempts - 1})", file=sys.stderr)
            time.sleep(wait)


def set_thumbnail(youtube, video_id: str, thumb: Path) -> None:
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumb), mimetype="image/png"),
        ).execute()
        print(f"[upload] 썸네일을 올렸다: {video_id}", file=sys.stderr)
    except HttpError as error:
        # 영상은 이미 올라갔다. 여기서 실행을 실패로 만들 값은 없다.
        print(f"[upload] 썸네일 실패 (무시): {error}", file=sys.stderr)


def load_build(directory: Path) -> tuple:
    """빌드 폴더에서 metadata 와 영상 경로를 꺼낸다."""
    meta_path = directory / "metadata.json"
    if not meta_path.exists():
        raise SystemExit(f"{directory} 에 metadata.json 이 없다")
    video = directory / "video.mp4"
    if not video.exists():
        raise SystemExit(f"{directory} 에 video.mp4 가 없다")
    return meta_path, json.loads(meta_path.read_text(encoding="utf-8")), video


def main() -> int:
    parser = argparse.ArgumentParser(description="만들어 둔 한 편을 올린다")
    parser.add_argument("--dir", required=True, type=Path,
                        help="video.mp4 와 metadata.json 이 있는 빌드 폴더")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"],
                        help="metadata 의 공개 설정을 덮어쓴다")
    parser.add_argument("--again", action="store_true",
                        help="이미 올린 폴더라도 한 편 더 올린다")
    args = parser.parse_args()

    meta_path, meta, video = load_build(args.dir)

    # 순서가 중요하다. 네트워크를 타기 전에 값싼 검사를 전부 끝낸다.
    assert_not_uploaded(meta, args.again)
    verify_before_upload(meta)

    youtube = youtube_client(os.environ)
    video_id = upload(youtube, video, meta, args.privacy or "")
    print(f"[upload] https://www.youtube.com/watch?v={video_id}", file=sys.stderr)

    thumb = args.dir / "thumbnail.png"
    if thumb.exists():
        set_thumbnail(youtube, video_id, thumb)

    playlist = (meta.get("playlist") or "").strip()
    if playlist:
        add_to_playlist(youtube, video_id, playlist)

    privacy = chosen_privacy(meta, args.privacy or "")

    meta["youtube_video_id"] = video_id
    # 올린 뒤의 metadata.json 은 "무엇이 나갔나"의 기록이다. 공개로 올렸는데
    # private 이 남아 있으면 나중에 그 파일을 보고 반대로 읽는다.
    meta["privacyStatus"] = privacy
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")

    # 올라간 뒤에 적는다. 올라가지 않은 영상은 발행이 아니다.
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")
    append_published(published_row(meta, video_id, privacy, now))

    if privacy != "public":
        print(f"[upload] 공개 설정: {privacy} — 확인하고 직접 공개할 것",
              file=sys.stderr)

    print(video_id)     # 표준 출력의 유일한 줄
    return 0


if __name__ == "__main__":
    sys.exit(main())
