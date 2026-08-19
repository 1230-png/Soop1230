# 🎵 Suno AI 마스터링 대시보드

**본인만 쓸 수 있는 개인 웹사이트** - Suno AI로 만든 감성 힙합을 관리하고 여러 YouTube 채널에 자동 업로드

![Status](https://img.shields.io/badge/status-ready-brightgreen)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-Personal%20Use-green)

---

## ✨ 주요 기능

### 🎵 Suno 곡 관리
- Suno 다운로드 폴더 자동 모니터링
- 곡 자동 임포트
- 메타데이터 관리 (제목, 설명, 아티스트 등)

### 🎚️ 마스터링 엔진
- **표준 마스터링** - 일반 음악
- **라우드 마스터링** - 큰 음량
- **Content ID 회피** - YouTube 저작권 필터 회피 처리
- FFmpeg 기반 고품질 처리

### 📺 YouTube 멀티 계정 관리
- 여러 브랜드 계정 동시 관리
- 각 계정별 독립적인 관리
- OAuth 2.0 기반 안전한 인증

### 🚀 자동 업로드
- 음악 + 이미지로 영상 생성
- 여러 계정에 동시 업로드
- 스케줄 업로드 가능

### 🔐 개인 보호
- 로그인 비밀번호 보호
- 본인만 접근 가능
- 로컬 데이터 저장

---

## 🚀 빠른 시작

### 1. 요구사항 설치

```bash
# Python 3.8+ 설치
# FFmpeg 설치

# Python 라이브러리 설치
pip install -r requirements.txt
```

### 2. 설정

```bash
# config.py에서 설정 변경
# - Suno 폴더 경로
# - 로그인 비밀번호
# - YouTube OAuth 정보
```

### 3. 실행

```bash
python app.py
```

### 4. 접속

```
http://localhost:5000
```

---

## 📖 상세 설명

자세한 설정 방법은 **[SETUP_GUIDE.md](SETUP_GUIDE.md)** 를 참고하세요!

---

## 🎯 사용 흐름

```
1. Suno에서 곡 생성
        ↓
2. 곡을 C:\Users\admin\Desktop\suno 에 다운로드
        ↓
3. 대시보드에서 "Suno 폴더 스캔" 클릭
        ↓
4. 곡이 자동 임포트됨
        ↓
5. 마스터링 처리 (표준/라우드/Content ID 회피)
        ↓
6. 이미지 + 음악으로 영상 생성
        ↓
7. YouTube 계정 선택
        ↓
8. "업로드" 클릭 → 완료!
```

---

## 🔧 기술 스택

- **프론트엔드**: HTML5, CSS3, Vanilla JavaScript
- **백엔드**: Flask 2.3.2
- **오디오 처리**: FFmpeg
- **YouTube API**: google-api-python-client
- **인증**: Flask-Session

---

## 📁 프로젝트 구조

```
suno-dashboard/
├── app.py                      # Flask 메인 앱
├── config.py                   # 설정 파일
├── requirements.txt            # Python 의존성
├── SETUP_GUIDE.md              # 설정 가이드
├── README.md                   # 이 파일
├── templates/                  # HTML 템플릿
│   ├── base.html              # 기본 레이아웃
│   ├── login.html             # 로그인 페이지
│   ├── dashboard.html         # 메인 대시보드
│   ├── settings.html          # 설정 페이지
│   └── error.html             # 에러 페이지
├── static/                     # 정적 파일
│   ├── css/
│   │   └── style.css          # 스타일시트
│   └── js/
│       └── main.js            # JavaScript
├── mastering/                  # 마스터링 엔진
│   ├── __init__.py
│   └── audio_processor.py     # 오디오 처리
├── youtube/                    # YouTube 통합
│   ├── __init__.py
│   └── uploader.py            # 업로드 관리
├── suno/                       # Suno 곡 관리
│   ├── __init__.py
│   └── importer.py            # 자동 임포트
├── data/                       # 저장된 데이터
│   ├── youtube_accounts.json  # YouTube 계정 정보
│   ├── suno_library.json      # 곡 라이브러리
│   └── youtube_credentials.json # OAuth 정보
└── logs/                       # 로그 파일
```

---

## ⚙️ 설정

### config.py

주요 설정:

```python
# 로그인 비밀번호
LOGIN_PASSWORD = 'admin1234'

# Suno 곡 폴더
SUNO_DOWNLOAD_FOLDER = r'C:\Users\admin\Desktop\suno'

# 마스터링 기본값
MASTERING_CONFIG = {
    'sample_rate': 44100,
    'normalization_target': -23.0,  # LUFS
}

# Content ID 회피 설정
ANTI_CONTENT_ID = {
    'eq_boost': [100, 150, 200, 300, 500, 1000],
    'eq_cut': [4000, 8000, 12000],
    'slight_pitch_shift': 0.02,
    'time_stretch': 0.98,
}
```

---

## 🔐 보안

- ✅ 로그인 보호
- ✅ 로컬 저장소 (외부 업로드 안 함)
- ✅ OAuth 2.0 기반 YouTube 인증
- ✅ 세션 기반 관리

---

## 🎨 화면

### 로그인 페이지
- 간단한 비밀번호 인증
- 우아한 디자인

### 대시보드
- 통계 카드 (총 곡, YouTube 계정, 오늘 임포트)
- 빠른 작업 버튼
- 최근 임포트된 곡 목록

### 곡 관리
- 모든 곡 목록
- 메타데이터 편집
- 마스터링 프리셋 선택

### YouTube 설정
- 계정 추가/삭제
- 각 계정 상태 확인

### 업로드
- 음악 파일 선택
- 썸네일 이미지 선택
- 제목/설명/태그 입력
- 계정 선택 후 업로드

---

## 🚀 배포 (선택사항)

로컬에서만 실행되지만, 필요시:

- **Windows 시작프로그램에 추가**: 배치 파일 생성
- **Docker**: Dockerfile 작성 후 컨테이너 배포

---

## 📝 라이선스

개인 사용 전용

---

## 💡 팁

- **정기 백업**: `data/` 폴더 백업
- **Content ID 회피**: 마스터링할 때 "Content ID 회피" 프리셋 사용
- **YouTube 제한**: 하루에 업로드 개수 제한이 있을 수 있음
- **FFmpeg**: 음질은 FFmpeg 설치 상태에 따라 결정됨

---

## 🆘 문제 해결

| 문제 | 해결 |
|------|------|
| Python이 인식되지 않음 | PATH 환경변수 확인 후 재부팅 |
| pip 오류 | `pip install --upgrade pip` 실행 |
| FFmpeg를 찾을 수 없음 | PATH에 FFmpeg 경로 추가 |
| 포트 5000 이미 사용 중 | config.py에서 포트 변경 |

---

**시작하기**: `python app.py` 를 실행하세요! 🎵

