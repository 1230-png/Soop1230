import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# 유튜브 업로드 및 채널 관리를 위한 전체 권한 스코프
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube']

def generate_brand_account_tokens():
    client_secret_file = 'client_secret.json'

    if not os.path.exists(client_secret_file):
        print(f"❌ 에러: {client_secret_file} 파일이 현재 디렉토리에 없습니다.")
        print("구글 클라우드 콘솔에서 데스크톱 앱용 비밀번호 JSON을 다운로드 받아 파일명을 변경해 주세요.")
        return

    # 모바일/서버 환경용 로컬 콘솔 흐름 빌드
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes=SCOPES)

    # ⚠️ 중요: 모바일에서는 자동 브라우저 오픈이 안 되므로 URL을 콘솔에 수동 표시합니다.
    # 사용자가 링크를 복사해 브라우저 인증 후, 결과 코드를 직접 터미널에 붙여넣는 방식입니다.
    print("\n" + "="*60)
    print("📢 아래 생성된 URL 링크를 전체 복사하여 모바일 브라우저(크롬 등)에 붙여넣으세요.")
    print("구글 로그인 시 반드시 목적지 [브랜드 계정]을 정확히 선택해야 합니다!")
    print("="*60 + "\n")

    # 로컬 서버를 열지 않고 터미널 코드로 입력받는 인증 방식 실행
    credentials = flow.run_local_server(
        host='localhost',
        port=8080,
        authorization_prompt_message='인증을 위해 다음 링크로 이동하세요: {url}',
        success_message='인증이 완료되었습니다. 터미널을 확인하세요.',
        open_browser=False
    )

    # 추출된 토큰 정보 정리
    token_data = {
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri
    }

    # 결과를 가독성 좋게 출력
    print("\n" + "✅" * 15 + " 토큰 추출 성공 " + "✅" * 15)
    print(f"📌 클라이언트 ID: {token_data['client_id']}")
    print(f"📌 클라이언트 시크릿: {token_data['client_secret']}")
    print(f"🔥 리프레시 토큰 (GitHub Secrets 등록용): {token_data['refresh_token']}")
    print("="*60)
    print("ℹ️ 위 refresh_token 값을 복사하여 깃허브 액션 Secrets에 저장하시면 영구 자동화가 가능합니다.")
    print("="*60 + "\n")

if __name__ == '__main__':
    generate_brand_account_tokens()
