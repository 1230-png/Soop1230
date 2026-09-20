"""「귀트는 일본어」 refresh token 발급 — **본인 컴퓨터에서** 한 번만 돌린다.

CI 에서 돌리지 않는다. 브라우저 로그인이 필요하고, 여기서 나오는 값이
그대로 시크릿이다.

    pip install google-auth-oauthlib

    # 1) 클라우드 콘솔에서 받은 JSON 으로
    python3 channel_jp/get_refresh_token.py \
        --client-secret-file client_secret.json --with-analytics

    # 2) JSON 없이 값으로
    python3 channel_jp/get_refresh_token.py \
        --client-id "...apps.googleusercontent.com" \
        --client-secret "GOCSPX-..." --with-analytics

`channel_200y3b/scripts/get_refresh_token.py` 와 하는 일이 같지만 **그것을
쓰면 안 된다.** 저쪽은 `Y3B_` 이름으로 찍고 "@200-y3b 로 로그인하라"고
안내한다 — 그대로 따라 하면 이 채널의 토큰을 저쪽 이름으로 넣거나, 저쪽
채널로 로그인해서 엉뚱한 채널의 토큰을 받는다. 되돌리기 번거로운 쪽이라
복사본을 둔다(CLAUDE.md — 디렉터리는 서로 독립이다).

**구글 클라우드 프로젝트가 서로 다르다.** 이 채널은 머니로직 때 쓰던
프로젝트를 그대로 쓴다. `yt-analytics.readonly` 를 동의 화면에 등록하는
것도 **그 프로젝트에서** 해야 한다 — 저쪽에 등록해 둔 것은 여기에 안 듣는다.

윈도우 PowerShell 에는 `python3` 가 없다. `python` 으로 부르고 경로는
역슬래시를 쓸 것.
"""

import argparse
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

PREFIX = "MV"

# youtube 가 아니라 force-ssl 이다. 상위 집합이라 업로드·재생목록·썸네일이
# 그대로 되면서 댓글까지 열린다. **지금 토큰보다 좁아지면 안 된다** — 좁은
# 토큰으로 갈아 끼우면 다음 화요일 cron 이 재생목록에서 403 으로 죽는다.
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

# 시청 시간·지속률은 Data API 에 없고 Analytics API 에 있다. 파트너 프로그램이
# 세는 4,000시간이 그것이라, 이것 없이는 수익화에 가까워지고 있는지 알 수 없다.
#
# 기본으로 켜지 않는다. 동의 화면에 등록되지 않은 스코프를 요청하면 발급
# **자체가** 실패하는데, 잘 돌고 있는 사람의 재발급을 깨뜨리는 쪽이 더 나쁘다.
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__)
    parser.add_argument("--client-secret-file",
                        help="클라우드 콘솔에서 받은 client_secret*.json 경로")
    parser.add_argument("--client-id", help="JSON 대신 값으로 넣을 때")
    parser.add_argument("--client-secret", help="JSON 대신 값으로 넣을 때")
    parser.add_argument("--with-analytics", action="store_true",
                        help="시청 시간·지속률을 읽는 권한도 함께 받는다. "
                             "동의 화면에 yt-analytics.readonly 를 먼저 "
                             "등록해 둘 것 — 없으면 발급이 실패한다.")
    args = parser.parse_args()

    scopes = [*SCOPES, ANALYTICS_SCOPE] if args.with_analytics else list(SCOPES)

    if args.client_id and args.client_secret:
        flow = InstalledAppFlow.from_client_config(
            {"installed": {
                "client_id": args.client_id,
                "client_secret": args.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }}, scopes)
    elif args.client_secret_file:
        flow = InstalledAppFlow.from_client_secrets_file(
            args.client_secret_file, scopes)
    else:
        parser.error("--client-secret-file 을 주거나, "
                     "--client-id 와 --client-secret 을 둘 다 줄 것.")

    print("브라우저가 열립니다. **「귀트는 일본어」를 관리하는 계정**으로 "
          "로그인하세요.\n"
          "    다른 채널로 로그인하면 그 채널의 토큰이 나오고, 다음 발행이 "
          "엉뚱한 채널로 올라갑니다.", file=sys.stderr)
    credentials = flow.run_local_server(port=0)

    granted = set(credentials.scopes or [])
    missing = [s for s in scopes if s not in granted]
    if missing:
        # 동의 화면에서 항목을 하나 끄면 이렇게 된다. 여기서 안 잡으면
        # 나중에 조용히 403 으로 실패한다.
        print(f"\n⚠️  부여되지 않은 권한이 있습니다: {', '.join(missing)}\n"
              f"    받은 것: {', '.join(sorted(granted)) or '(없음)'}\n"
              "    동의 화면에서 항목을 끄지 말고 다시 실행하세요.",
              file=sys.stderr)

    print("\nGitHub 저장소 Secrets 에 넣을 값 "
          "(Settings → Secrets and variables → Actions):\n")
    print(f"{PREFIX}_CLIENT_ID     {credentials.client_id}")
    print(f"{PREFIX}_CLIENT_SECRET {credentials.client_secret}")
    print(f"{PREFIX}_REFRESH_TOKEN {credentials.refresh_token}")
    print(f"\n세 값이 이미 등록돼 있다면 {PREFIX}_REFRESH_TOKEN 만 바꾸면 됩니다.")
    print("바꾼 뒤 「귀트는 일본어 — 채널 설명·키워드」 워크플로를 dry-run 으로 "
          "한 번 돌려 보세요. 토큰이 멀쩡한지 돈 안 쓰고 확인됩니다.")


if __name__ == "__main__":
    main()
