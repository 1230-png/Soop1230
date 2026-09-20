"""채널 설명·키워드·기본 언어를 채운다.

**비어 있는 칸만 채운다.** 사람이 손으로 적어 둔 값을 코드가 덮어쓰면, 그
사람은 자기가 무엇을 잃었는지도 모른 채 되돌려야 한다. 일부러 갈아 끼우려면
`--force` 를 줄 것.

`channel_200y3b/scripts/update_channel_settings.py` 와 같은 일을 하지만 코드를
가져다 쓰지 않는다(CLAUDE.md — 디렉터리는 서로 독립이다). 두 군데가 다르다.

1. **채널 ID 를 코드에 박지 않는다.** `MV_CHANNEL_ID` 가 없으면 자격 증명이
   실제로 가진 채널 ID 를 찍어 주고 멈춘다 — `upload.py` 와 같은 규칙이다.
2. **새로고침에 스코프를 싣지 않는다.** 저쪽은 `SCOPES = ["youtube"]` 를
   그대로 넘기는데, 발급 때보다 넓은 스코프를 보내면 구글이 invalid_scope 로
   거절한다. 스코프는 코드가 아니라 토큰에 붙어 있다(`upload.py` 주석).

    python3 channel_jp/channel_settings.py            # 빈 칸만 채운다
    python3 channel_jp/channel_settings.py --dry-run  # 무엇이 바뀌는지만 본다
"""

import argparse
import os
import sys

PREFIX = "MV"
CHANNEL_ID_ENV = f"{PREFIX}_CHANNEL_ID"

# 유튜브가 서버에서 거절하는 한도. 넘으면 업데이트가 통째로 실패한다.
KEYWORDS_MAX = 500
DESCRIPTION_MAX = 1000

# 검색어는 **한국어로만** 간다. 시청자가 한국어 화자이기 때문이다. 일본어
# 검색어를 넣으면 한국어를 배우는 일본인이 딸려 오는데, 이 채널의 설명과 뜻이
# 전부 한국어라 그 사람들에게는 쓸모가 없고 지속률만 깎는다.
#
# 롱폼 검색어를 앞에 둔다. 앞쪽에 가중치가 있고, 시청 시간이 쌓이는 자리가
# 롱폼이다(쇼츠 시청 시간은 파트너 프로그램 3,000시간에 안 들어간다).
KEYWORDS = [
    # 이 채널이 실제로 만드는 것
    "일본어듣기", "일본어리스닝", "일본어흘려듣기", "흘려듣기",
    "자면서듣는일본어", "잠들기전일본어", "수면일본어", "일본어몰아듣기",
    "일본어쉐도잉", "쉐도잉", "일본어따라말하기", "상황별일본어",
    # 배우는 사람이 치는 말
    "일본어공부", "일본어회화", "일본어독학", "일본어초보", "일본어기초",
    "일본어표현", "생활일본어", "일본어문장", "일본어단어", "일본어발음",
    "일본어공부혼자하기", "일본어회화연습", "일본어공부법", "일본어패턴",
    "일본어한마디", "히라가나", "가타카나", "일본어스피킹",
    # 쓰임새
    "여행일본어", "일본여행회화", "비즈니스일본어", "JLPT", "일본어시험",
    # 영어권 유입
    "learn japanese", "japanese listening", "japanese shadowing",
]

DESCRIPTION = (
    "귀트는 일본어 — 한국어로 뜻을 알려주는 일본어 듣기 채널입니다.\n"
    "\n"
    "[ 업로드 일정 ]\n"
    "매주 화요일 21시 — 상황별 일본어 (약 12분)\n"
    "매주 목요일 21시 — 쉐도잉 트레이닝, 따라 말하기 (약 20분)\n"
    "매주 금요일 21시 — 자면서 듣는 일본어 (약 35분)\n"
    "\n"
    "[ 이렇게 만들었습니다 ]\n"
    "일본어 문장 → 한국어 뜻 → 느린 일본어 순서로 반복됩니다.\n"
    "읽는 소리를 한글로 같이 적어 두어서, 가나를 아직 못 읽어도 따라 할 수 있습니다.\n"
    "화면만 봐도 되고, 소리만 들어도 됩니다.\n"
    "\n"
    "출퇴근길에 틀어놓고, 잠들기 전에 흘려듣기만 해도 귀가 열립니다.\n"
    "공항·식당·호텔·쇼핑·길찾기·긴급 상황까지, 그 자리에서 바로 나오는 문장을\n"
    "통째로 익히세요.\n"
    "\n"
    "#일본어공부 #일본어회화 #일본어듣기 #일본어쉐도잉 #자면서듣는일본어 #일본어독학"
)


class SettingsError(RuntimeError):
    pass


def format_keywords(keywords) -> str:
    """띄어쓰기로 잇되, 공백이 든 말만 따옴표로 묶는다.

    전부 묶으면 500자 한도에서 말마다 두 글자씩 그냥 버린다.
    """
    return " ".join(f'"{kw}"' if " " in kw else kw for kw in keywords)


def check_limits(keywords: str, description: str) -> None:
    """한도를 넘으면 **보내기 전에** 멈춘다.

    넘긴 채로 보내면 유튜브가 요청 전체를 거절해서, 멀쩡한 칸까지 같이 안 들어간다.
    """
    if len(keywords) > KEYWORDS_MAX:
        raise SettingsError(
            f"키워드가 {len(keywords)}자다 — 한도 {KEYWORDS_MAX}자를 넘는다")
    if len(description) > DESCRIPTION_MAX:
        raise SettingsError(
            f"설명이 {len(description)}자다 — 한도 {DESCRIPTION_MAX}자를 넘는다")


def field(branding: dict, name: str) -> str:
    return (branding.get(name) or "").strip()


def plan_changes(branding: dict, force: bool) -> tuple:
    """(바꾼 branding, 무엇을 바꿨는지) — 네트워크를 타지 않는다.

    나눠 둔 이유는 이 판단이 테스트할 값이 있는 부분이기 때문이다. 유튜브를
    부르는 쪽은 한 줄이고, 틀리면 눈에 보인다. 조용히 틀리는 쪽은 여기다.
    """
    branding = {**branding, "channel": {**branding.get("channel", {})}}
    channel = branding["channel"]
    changes = []

    keywords = format_keywords(KEYWORDS)
    check_limits(keywords, DESCRIPTION)

    if force or not field(channel, "keywords"):
        channel["keywords"] = keywords
        changes.append(f"키워드 ({len(KEYWORDS)}개, {len(keywords)}자)")
    if force or not field(channel, "description"):
        channel["description"] = DESCRIPTION
        changes.append(f"설명 ({len(DESCRIPTION)}자)")
    if not field(channel, "defaultLanguage"):
        # 한국어 화자에게 추천되어야 한다. 일본어를 가르치지만 설명과 뜻이
        # 한국어다 — upload.py 가 영상마다 ko 로 적는 것과 같은 이유다.
        channel["defaultLanguage"] = "ko"
        changes.append("기본 언어 (ko)")

    return branding, changes


def assert_right_channel(channel: dict, env) -> None:
    """남의 채널 설명을 갈아 끼우지 않는다.

    upload.py 와 같은 규칙이다 — 채널 ID 를 코드에 박지 않고, 시크릿이 없으면
    짐작하지 않고 멈춘다. 여기서 틀리면 되돌리기가 특히 번거롭다.
    """
    expected = (env.get(CHANNEL_ID_ENV) or "").strip()
    actual = channel["id"]
    title = channel.get("snippet", {}).get("title", "?")
    if not expected:
        raise SettingsError(
            f"{CHANNEL_ID_ENV} 가 없다. 이 자격 증명이 가진 채널은:\n"
            f"    {actual}  ({title})\n"
            f"맞으면 이 값을 {CHANNEL_ID_ENV} 시크릿에 넣고 다시 돌릴 것.")
    if expected != actual:
        raise SettingsError(
            f"자격 증명이 가리키는 채널({actual}, {title})이 "
            f"{CHANNEL_ID_ENV}({expected}) 와 다르다. 고치지 않는다.")


def youtube_client(env):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    missing = [f"{PREFIX}_{n}" for n in ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN")
               if not (env.get(f"{PREFIX}_{n}") or "").strip()]
    if missing:
        raise SettingsError(
            f"자격 증명이 없다 — {', '.join(missing)}. "
            "공용 YT_* 로 넘어가지 않는다(CLAUDE.md).")

    creds = Credentials(
        token=None,
        refresh_token=env[f"{PREFIX}_REFRESH_TOKEN"].strip(),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=env[f"{PREFIX}_CLIENT_ID"].strip(),
        client_secret=env[f"{PREFIX}_CLIENT_SECRET"].strip(),
        # 스코프를 싣지 않는다 — upload.py 주석을 볼 것.
        scopes=None)
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--force", action="store_true",
                        help="이미 적혀 있어도 덮어쓴다 (일부러 갈아 끼울 때만)")
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
        branding, changes = plan_changes(
            channel.get("brandingSettings", {}), args.force)
    except SettingsError as error:
        print(f"채널 설정을 고치지 않는다: {error}", file=sys.stderr)
        return 1

    if not changes:
        print("채워 넣을 것이 없다 — 이미 적혀 있다. 갈아 끼우려면 --force.")
        return 0

    print(f"바꿀 것: {', '.join(changes)}")
    if args.dry_run:
        print("--dry-run 이라 보내지 않았다.")
        return 0

    youtube.channels().update(
        part="brandingSettings",
        body={"id": channel["id"], "brandingSettings": branding}).execute()
    print(f"채널 {channel['id']} 에 넣었다: {', '.join(changes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
