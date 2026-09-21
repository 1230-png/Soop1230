"""채널 이름·설명·키워드를 `channel.yaml` 에 적힌 값으로 맞춘다.

    python3 channel_earth/channel_settings.py --dry-run   # 무엇이 바뀌는지만
    python3 channel_earth/channel_settings.py --force     # 실제로 갈아 끼운다

`channel_jp/channel_settings.py` 와 같은 일을 하지만 코드를 가져다 쓰지 않는다
(CLAUDE.md — 디렉터리는 서로 독립이다). 두 군데가 다르다.

1. **값을 코드에 박지 않고 `channel.yaml` 에서 읽는다.** 저쪽은 설명문이
   파이썬 문자열로 들어 있어, 문구를 고치려면 코드를 고쳐야 한다. 여기서는
   사람이 읽고 쓰는 곳이 한 군데다.
2. **`--force` 가 사실상 기본 경로다.** 이 채널은 새로 만든 것이 아니라
   @Rush22 의 방향을 바꾼 것이라, 설명란에 **예전 채널의 문구가 이미 적혀
   있다.** 빈 칸만 채우는 기본 동작으로는 아무것도 안 바뀐다. 그래도 기본값을
   바꾸지 않은 이유는, 실수로 돌렸을 때 남의 글을 지우지 않기 위해서다.

채널 이름(title)까지 바꾸는 것이 `channel_jp` 판에는 없다. 그쪽은 이름이
이미 맞았고 여기는 「머니러시」에서 「지구의 오늘」로 갈아야 한다.

**채널 이름을 바꿔도 채널 ID 는 그대로다.** 그래서 `RUSH_*` 자격 증명이
그대로 맞고, 시크릿을 다시 만들 필요가 없다.
"""

import argparse
import os
import sys
from pathlib import Path

import yaml
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build as build_service

ROOT = Path(__file__).resolve().parent
CHANNEL_FILE = ROOT / "channel.yaml"

# 새로고침 요청에 스코프를 실어 보내지 않는다. 발급 때보다 넓은 스코프를
# 보내면 구글이 invalid_scope 로 거절한다 — 스코프는 코드가 아니라 토큰에
# 붙어 있다(upload.py 의 같은 주석).
SCOPES = None

PREFIX = "RUSH"
CHANNEL_ID_ENV = f"{PREFIX}_CHANNEL_ID"
CREDENTIAL_NAMES = ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN")

# 유튜브가 서버에서 거절하는 한도. 넘으면 업데이트가 통째로 실패해서
# 멀쩡한 칸까지 같이 안 들어간다.
TITLE_MAX = 100
KEYWORDS_MAX = 500
DESCRIPTION_MAX = 1000


class SettingsError(RuntimeError):
    pass


def load_channel() -> dict:
    return (yaml.safe_load(CHANNEL_FILE.read_text(encoding="utf-8")) or {})["channel"]


def format_keywords(keywords) -> str:
    """띄어쓰기로 잇되, 공백이 든 말만 따옴표로 묶는다.

    전부 묶으면 500자 한도에서 말마다 두 글자씩 그냥 버린다.
    """
    return " ".join(f'"{kw}"' if " " in kw else kw for kw in keywords)


def check_limits(title: str, keywords: str, description: str) -> None:
    for name, value, cap in (("이름", title, TITLE_MAX),
                             ("키워드", keywords, KEYWORDS_MAX),
                             ("설명", description, DESCRIPTION_MAX)):
        if len(value) > cap:
            raise SettingsError(f"{name}이 {len(value)}자다 — 한도 {cap}자를 넘는다")


def field(section: dict, name: str) -> str:
    return (section.get(name) or "").strip()


def plan_changes(branding: dict, wanted: dict, force: bool) -> tuple:
    """(바꾼 branding, 무엇을 바꿨는지) — 네트워크를 타지 않는다.

    나눠 둔 이유는 이 판단이 테스트할 값이 있는 부분이기 때문이다. 유튜브를
    부르는 쪽은 한 줄이고 틀리면 눈에 보인다. 조용히 틀리는 쪽은 여기다.
    """
    branding = {**branding, "channel": {**branding.get("channel", {})}}
    channel = branding["channel"]
    changes = []

    title = (wanted.get("name") or "").strip()
    description = (wanted.get("description") or "").strip()
    keywords = format_keywords(wanted.get("keywords") or [])
    check_limits(title, keywords, description)

    for key, value, label in (
            ("title", title, "이름"),
            ("description", description, f"설명 ({len(description)}자)"),
            ("keywords", keywords, f"키워드 ({len(keywords)}자)")):
        if not value:
            continue
        current = field(channel, key)
        if current == value:
            continue
        if current and not force:
            # 이미 적혀 있는데 --force 가 없다. 이 채널에서는 거의 항상
            # 이쪽이다 — 예전 「머니러시」 문구가 남아 있기 때문이다.
            changes.append(f"[건너뜀] {label} — 이미 적혀 있다 (--force 필요)")
            continue
        channel[key] = value
        changes.append(f"{label}{' (덮어씀)' if current else ''}")

    if not field(channel, "defaultLanguage"):
        # 한국어 시청자에게 추천되어야 한다. 화면에 말은 없지만 제목과 설명이
        # 한국어다 — upload.py 가 영상마다 ko 로 적는 것과 같은 이유다.
        channel["defaultLanguage"] = "ko"
        changes.append("기본 언어 (ko)")

    return branding, changes


def credentials(env) -> dict:
    values, missing = {}, []
    for name in CREDENTIAL_NAMES:
        value = (env.get(f"{PREFIX}_{name}") or "").strip()
        if value:
            values[name] = value
        else:
            missing.append(f"{PREFIX}_{name}")
    if missing:
        raise SettingsError("자격 증명이 없다: " + ", ".join(missing))
    return values


def assert_right_channel(channel: dict, env) -> None:
    """남의 채널 설명을 갈아 끼우지 않는다.

    upload.py 와 같은 규칙이다 — 채널 ID 를 코드에 박지 않고, 시크릿이 없으면
    짐작하지 않고 멈춘다. 여기서 틀리면 되돌리기가 특히 번거롭다.
    """
    actual = channel["id"]
    expected = (env.get(CHANNEL_ID_ENV) or "").strip()
    title = channel.get("snippet", {}).get("title", "?")
    if not expected:
        raise SettingsError(
            f"{CHANNEL_ID_ENV} 가 없다. 이 자격 증명이 가진 채널은:\n"
            f"  {actual}  ({title})\n"
            f"맞으면 이 값을 {CHANNEL_ID_ENV} 에 넣고 다시 돌릴 것.")
    if actual != expected:
        raise SettingsError(
            f"자격 증명은 {actual} ({title}) 의 것인데 "
            f"{CHANNEL_ID_ENV} 는 {expected} 이다.")


def youtube_client(env):
    values = credentials(env)
    creds = Credentials(
        token=None, refresh_token=values["REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=values["CLIENT_ID"], client_secret=values["CLIENT_SECRET"],
        scopes=SCOPES)
    try:
        creds.refresh(Request())
    except RefreshError as error:
        raise SettingsError(
            f"{PREFIX}_* 자격 증명으로 인증하지 못했다: {error}\n"
            "리프레시 토큰이 취소됐거나, CLIENT_ID/SECRET 이 그 토큰을 발급한\n"
            "구글 클라우드 프로젝트의 것이 아니다.") from error
    return build_service("youtube", "v3", credentials=creds)


def main() -> int:
    parser = argparse.ArgumentParser(description="채널 이름·설명·키워드 맞추기")
    parser.add_argument("--force", action="store_true",
                        help="이미 적혀 있어도 덮어쓴다 (방향을 바꿀 때 필요)")
    parser.add_argument("--dry-run", action="store_true",
                        help="무엇이 바뀌는지만 찍고 보내지 않는다")
    args = parser.parse_args()

    try:
        youtube = youtube_client(os.environ)
        response = youtube.channels().list(
            part="brandingSettings,snippet", mine=True).execute()
        items = response.get("items", [])
        if not items:
            raise SettingsError("이 자격 증명이 채널을 가리키지 않는다")

        channel = items[0]
        assert_right_channel(channel, os.environ)
        print(f"[설정] 지금 이름: {channel['snippet'].get('title', '?')}",
              file=sys.stderr)
        branding, changes = plan_changes(
            channel.get("brandingSettings", {}), load_channel(), args.force)
    except SettingsError as error:
        print(f"채널 설정을 고치지 않는다: {error}", file=sys.stderr)
        return 1

    if not changes:
        print("바꿀 것이 없다 — 이미 맞다.")
        return 0

    for line in changes:
        print(f"  {line}")
    if args.dry_run:
        print("--dry-run 이라 보내지 않았다.")
        return 0
    if all(line.startswith("[건너뜀]") for line in changes):
        print("전부 건너뛰었다 — 갈아 끼우려면 --force 를 줄 것.")
        return 0

    youtube.channels().update(
        part="brandingSettings",
        body={"id": channel["id"], "brandingSettings": branding}).execute()
    print(f"채널 {channel['id']} 에 넣었다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
