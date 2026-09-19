"""YouTube refresh token 발급 — 본인 컴퓨터에서 한 번만 돌린다 (CI 아님).

두 가지 방법 중 편한 쪽으로:

    # 1) Cloud Console 에서 받은 JSON 으로
    pip install google-auth-oauthlib
    python3 get_refresh_token.py --client-secret-file client_secret.json

    # 2) 클라이언트 ID·보안 비밀번호를 직접 입력해서 (JSON 안 받아도 됨)
    python3 get_refresh_token.py --client-id "1234-abc.apps.googleusercontent.com" \
                                 --client-secret "GOCSPX-..."

윈도우 PowerShell 에서는 `python3` 가 없다. `python` 으로 부르고 경로 구분자도
역슬래시를 쓸 것 — `python scripts\\get_refresh_token.py ...`

브라우저가 열리면 반드시 @200-y3b 를 관리하는 계정으로 로그인할 것.
자세한 순서는 ../SETUP.md 참고.
"""

import argparse
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

# youtube 대신 force-ssl. 상위 집합이라 업로드·재생목록·썸네일이 그대로
# 되면서 댓글(commentThreads)까지 열린다. youtube 만으로는 댓글이
# 403 insufficientPermissions 로 막힌다.
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

# 시청 시간·유지율은 Data API 에 없고 Analytics API 에 있다. 파트너 프로그램이
# 세는 3,000시간이 그것이라, 이것 없이는 수익화에 가까워지고 있는지 알 수 없다
# (조회수로는 알 수 없다 — 숏폼은 조회수가 잘 늘면서 그 시간에는 안 들어간다).
#
# 기본으로 켜지 않는다. 클라우드 콘솔 동의 화면에 등록되지 않은 스코프를
# 요청하면 발급 자체가 실패하는데, 지금 잘 돌고 있는 사람의 재발급을 깨뜨리는
# 것이 더 나쁘다. 콘솔에 넣고 나서 --with-analytics 로 켤 것.
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__)
    parser.add_argument("--client-secret-file",
                        help="Cloud Console 에서 받은 client_secret*.json 경로")
    parser.add_argument("--client-id", help="JSON 대신 값으로 넣을 때")
    parser.add_argument("--client-secret", help="JSON 대신 값으로 넣을 때")
    parser.add_argument("--with-analytics", action="store_true",
                        help="시청 시간을 읽는 권한도 함께 받는다. 클라우드 콘솔 "
                             "동의 화면에 yt-analytics.readonly 를 먼저 "
                             "등록해 둘 것 — 없으면 발급이 실패한다.")
    args = parser.parse_args()

    scopes = [*SCOPES, ANALYTICS_SCOPE] if args.with_analytics else list(SCOPES)

    if args.client_id and args.client_secret:
        # JSON 을 내려받지 않아도 되게 같은 모양을 메모리에서 만든다.
        flow = InstalledAppFlow.from_client_config(
            {"installed": {
                "client_id": args.client_id,
                "client_secret": args.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }},
            scopes,
        )
    elif args.client_secret_file:
        flow = InstalledAppFlow.from_client_secrets_file(
            args.client_secret_file, scopes)
    else:
        parser.error(
            "--client-secret-file 로 JSON 을 주거나, "
            "--client-id 와 --client-secret 을 둘 다 줄 것.")

    print("브라우저가 열립니다. @200-y3b 를 관리하는 계정으로 로그인하세요.",
          file=sys.stderr)
    credentials = flow.run_local_server(port=0)

    granted = set(credentials.scopes or [])
    for needed in scopes:
        if needed not in granted:
            # 동의 화면에서 항목을 하나 끄면 이렇게 된다. 여기서 잡지 않으면
            # 나중에 댓글이 403 으로 조용히 실패한다.
            print(f"\n⚠️  {needed} 가 부여되지 않았습니다: {granted or '(없음)'}\n"
                  "    동의 화면에서 항목을 끄지 말고 다시 실행하세요.",
                  file=sys.stderr)

    print("\nGitHub 저장소 Secrets 에 넣을 값 "
          "(Settings → Secrets and variables → Actions):\n")
    print(f"Y3B_CLIENT_ID     {credentials.client_id}")
    print(f"Y3B_CLIENT_SECRET {credentials.client_secret}")
    print(f"Y3B_REFRESH_TOKEN {credentials.refresh_token}")
    print("\n세 값이 이미 등록돼 있다면 Y3B_REFRESH_TOKEN 만 바꾸면 됩니다.")


if __name__ == "__main__":
    main()
