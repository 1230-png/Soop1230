import os
import pickle
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.api_core.retry import Retry
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import YOUTUBE_CREDENTIALS_FILE, YOUTUBE_TOKEN_FILE, DATA_FOLDER

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

class YouTubeUploader:
    """여러 YouTube 계정 관리 및 업로드"""

    def __init__(self):
        self.accounts_file = os.path.join(DATA_FOLDER, 'youtube_accounts.json')
        self.load_accounts()

    def load_accounts(self):
        """저장된 YouTube 계정 불러오기"""
        if os.path.exists(self.accounts_file):
            with open(self.accounts_file, 'r') as f:
                self.accounts = json.load(f)
        else:
            self.accounts = {}

    def save_accounts(self):
        """YouTube 계정 저장"""
        with open(self.accounts_file, 'w') as f:
            json.dump(self.accounts, f, indent=2)

    def authenticate(self, account_name, client_id, client_secret):
        """
        새로운 YouTube 계정 인증
        client_id, client_secret은 Google Cloud OAuth 정보
        """
        try:
            # OAuth 설정 파일 생성
            oauth_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost:5000/auth/callback"]
                }
            }

            config_file = os.path.join(DATA_FOLDER, f'{account_name}_oauth.json')
            with open(config_file, 'w') as f:
                json.dump(oauth_config, f)

            # 인증 플로우 실행
            flow = InstalledAppFlow.from_client_secrets_file(
                config_file,
                SCOPES
            )

            creds = flow.run_local_server(port=8080)

            # 계정 정보 저장
            self.accounts[account_name] = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'client_id': client_id,
                'client_secret': client_secret,
                'channel_id': self.get_channel_info(creds)['id']
            }

            self.save_accounts()
            return {'success': True, 'message': f'{account_name} 계정 연동 완료'}

        except Exception as e:
            return {'success': False, 'message': str(e)}

    def get_service(self, account_name):
        """YouTube API 서비스 객체 반환"""
        if account_name not in self.accounts:
            return None

        account = self.accounts[account_name]

        # 토큰이 만료되었는지 확인하고 갱신
        creds = Credentials(
            token=account['token'],
            refresh_token=account['refresh_token'],
            client_id=account['client_id'],
            client_secret=account['client_secret'],
            token_uri='https://oauth2.googleapis.com/token'
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            account['token'] = creds.token
            self.save_accounts()

        return build('youtube', 'v3', credentials=creds)

    def upload_video(self, account_name, video_file, title, description, tags=None, category_id='10', privacy_status='public'):
        """
        YouTube에 영상 업로드
        category_id: 10=음악, 24=설명 등
        privacy_status: 'public', 'unlisted', 'private'
        """
        try:
            service = self.get_service(account_name)
            if not service:
                return {'success': False, 'message': f'{account_name} 계정을 찾을 수 없습니다'}

            # 영상 메타데이터
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags or ['suno', 'ai', 'music'],
                    'categoryId': category_id
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'madeForKids': False
                }
            }

            # 파일 업로드
            media = MediaFileUpload(video_file, chunksize=-1, resumable=True)

            request = service.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )

            response = request.execute()

            return {
                'success': True,
                'message': '업로드 완료',
                'video_id': response['id'],
                'url': f'https://www.youtube.com/watch?v={response["id"]}'
            }

        except Exception as e:
            return {'success': False, 'message': str(e)}

    def get_channel_info(self, creds):
        """채널 정보 조회"""
        service = build('youtube', 'v3', credentials=creds)
        request = service.channels().list(
            part='id,snippet',
            mine=True
        )
        response = request.execute()

        if response['items']:
            return {
                'id': response['items'][0]['id'],
                'title': response['items'][0]['snippet']['title'],
                'thumbnail': response['items'][0]['snippet']['thumbnails']['default']['url']
            }
        return {}

    def list_accounts(self):
        """저장된 계정 목록"""
        return list(self.accounts.keys())

    def delete_account(self, account_name):
        """계정 삭제"""
        if account_name in self.accounts:
            del self.accounts[account_name]
            self.save_accounts()
            return {'success': True, 'message': f'{account_name} 계정 삭제됨'}
        return {'success': False, 'message': '계정을 찾을 수 없습니다'}
