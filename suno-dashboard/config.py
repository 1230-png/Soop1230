import os
import json
from pathlib import Path

# 기본 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY = 'suno-dashboard-secret-key-2024'

# 세션 설정
SESSION_TYPE = 'filesystem'
PERMANENT_SESSION_LIFETIME = 86400 * 7  # 7일

# 파일 경로
SUNO_DOWNLOAD_FOLDER = r'C:\Users\admin\Desktop\suno'  # 사용자의 Suno 폴더
DATA_FOLDER = os.path.join(BASE_DIR, 'data')
LOGS_FOLDER = os.path.join(BASE_DIR, 'logs')

# 폴더 생성
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(LOGS_FOLDER, exist_ok=True)

# YouTube OAuth 설정 파일 경로
YOUTUBE_CREDENTIALS_FILE = os.path.join(DATA_FOLDER, 'youtube_credentials.json')
YOUTUBE_TOKEN_FILE = os.path.join(DATA_FOLDER, 'youtube_token.json')

# 마스터링 설정
MASTERING_CONFIG = {
    'sample_rate': 44100,
    'bit_depth': 16,
    'normalization_target': -23.0,  # LUFS
    'max_loudness': -1.0,  # dB
}

# Content ID 회피용 오디오 처리
ANTI_CONTENT_ID = {
    'eq_boost': [100, 150, 200, 300, 500, 1000],  # Hz
    'eq_cut': [4000, 8000, 12000],
    'slight_pitch_shift': 0.02,  # 약간의 피치 변화
    'time_stretch': 0.98,  # 98% 속도 (거의 안 들림)
}

# 로그인 비밀번호 (사용자 설정)
LOGIN_PASSWORD = 'admin1234'  # 나중에 변경하세요!
