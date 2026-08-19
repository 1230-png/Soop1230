# 🎵 Suno AI 마스터링 대시보드 - 설정 가이드

본인만 쓸 수 있는 개인 대시보드입니다. **완전 초보자도 따라하면 됩니다!**

---

## 📋 준비물

- Windows/Mac/Linux 컴퓨터
- 인터넷 연결
- 약 10분의 시간

---

## 🚀 설치 (5단계)

### 1단계: Python 설치

**Windows:**
1. https://www.python.org/downloads/ 방문
2. "Download Python 3.11" 클릭
3. 다운로드된 파일 실행
4. ✅ **"Add Python to PATH" 체크** (중요!)
5. "Install Now" 클릭
6. 설치 완료 대기

**Mac:**
```bash
brew install python3
```

**Linux (Ubuntu):**
```bash
sudo apt-get install python3 python3-pip
```

### 2단계: FFmpeg 설치 (마스터링용)

**Windows:**
1. https://ffmpeg.org/download.html 방문
2. Windows 빌드 다운로드
3. 압축 해제
4. C:\ffmpeg 폴더에 저장
5. 환경변수 PATH에 추가:
   - 시작 → "환경변수" 검색
   - "시스템 환경 변수 편집" 클릭
   - "환경 변수" 버튼 클릭
   - PATH 선택 → "편집"
   - "새로 만들기" → `C:\ffmpeg\bin` 추가

**Mac:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt-get install ffmpeg
```

### 3단계: Python 라이브러리 설치

폴더에서 **명령 프롬프트/터미널** 열기:

```bash
# Windows에서 cmd 열기:
# 폴더 열기 → 위 주소창 클릭 → "cmd" 입력 → Enter

pip install -r requirements.txt
```

이제 필요한 라이브러리가 모두 설치됩니다.

### 4단계: YouTube OAuth 설정

**이미 준비한 클라이언트 ID/시크릿으로:**

`data/youtube_credentials.json` 파일 생성:

```json
{
  "installed": {
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "YOUR_CLIENT_SECRET",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": ["http://localhost:5000/auth/callback"]
  }
}
```

> 👉 `YOUR_CLIENT_ID`와 `YOUR_CLIENT_SECRET`을 아까 받은 실제 값으로 바꾸세요!

### 5단계: 웹사이트 실행

명령 프롬프트/터미널에서:

```bash
python app.py
```

이렇게 나타나면 성공! 👇

```
==================================================
🎵 Suno AI 마스터링 대시보드
==================================================
📁 Suno 폴더: C:\Users\admin\Desktop\suno
🔑 로그인 비밀번호: admin1234
🌐 웹사이트: http://localhost:5000
==================================================
```

**브라우저에서 열기:**
```
http://localhost:5000
```

---

## 🔐 로그인

**비밀번호:** `admin1234`

> ⚠️ 처음 로그인 후 `config.py`에서 비밀번호 변경하세요!

---

## 📱 사용 방법

### Suno 곡 추가하기

1. Suno (suno.ai)에서 곡 생성
2. 곡 다운로드 → **`C:\Users\admin\Desktop\suno` 폴더**에 저장
3. 대시보드 → "📁 Suno 폴더 스캔" 클릭
4. 자동으로 곡이 임포트됨!

### 곡 마스터링

1. 대시보드 → "🎵 곡 관리"
2. 곡 선택
3. "🎚️ 마스터링" 클릭
4. 프리셋 선택:
   - **표준**: 일반 음악
   - **라우드**: 큰 음량
   - **Content ID 회피**: YouTube 저작권 필터 회피 처리

### YouTube 계정 추가

1. 설정 → "📺 YouTube 계정"
2. "+ 계정 추가" 클릭
3. Google Cloud 클라이언트 ID/시크릿 입력
4. "추가" 클릭
5. Google 계정으로 로그인

### 영상 업로드

1. 대시보드 → "🚀 업로드"
2. 음악 + 썸네일 이미지 선택
3. 제목/설명 입력
4. 계정 선택
5. "업로드" 클릭

---

## ⚙️ 설정 변경

### 로그인 비밀번호 변경

`config.py` 열기 → 아래 줄 찾기:

```python
LOGIN_PASSWORD = 'admin1234'  # 나중에 변경하세요!
```

원하는 비밀번호로 변경:

```python
LOGIN_PASSWORD = '내비밀번호'
```

저장 후 웹사이트 다시 시작.

### Suno 폴더 경로 변경

`config.py` 열기 → 아래 줄 찾기:

```python
SUNO_DOWNLOAD_FOLDER = r'C:\Users\admin\Desktop\suno'
```

원하는 경로로 변경:

```python
SUNO_DOWNLOAD_FOLDER = r'C:\Users\당신이름\Downloads'
```

---

## 🐛 문제 해결

### "python이 인식되지 않습니다"
→ Python 설치 후 컴퓨터 재부팅 필요

### "pip install 오류"
→ `pip install --upgrade pip` 실행 후 다시 시도

### "FFmpeg를 찾을 수 없습니다"
→ FFmpeg 설치 경로를 PATH 환경변수에 추가했는지 확인

### "포트 5000이 이미 사용 중입니다"
→ `config.py`에서 포트 번호 변경 (5000 → 5001)

---

## 📚 파일 구조

```
suno-dashboard/
├── app.py                 # 메인 웹앱
├── config.py              # 설정 파일
├── requirements.txt       # Python 라이브러리
├── templates/             # HTML 페이지
│   ├── login.html
│   ├── dashboard.html
│   └── ...
├── static/                # CSS, JavaScript
│   ├── css/
│   └── js/
├── mastering/             # 마스터링 엔진
│   └── audio_processor.py
├── youtube/               # YouTube 업로드
│   └── uploader.py
├── suno/                  # Suno 곡 임포트
│   └── importer.py
├── data/                  # 저장된 데이터
│   ├── youtube_accounts.json
│   ├── suno_library.json
│   └── youtube_credentials.json
└── logs/                  # 로그 파일
```

---

## 🎯 주요 기능

✅ **로그인 보호** - 본인만 접근 가능  
✅ **Suno 자동 임포트** - 다운로드 폴더 자동 모니터링  
✅ **마스터링** - FFmpeg 기반 음질 최적화  
✅ **Content ID 회피** - YouTube 저작권 필터 회피 처리  
✅ **여러 YouTube 계정** - 다중 채널 관리  
✅ **자동 업로드** - 스케줄 업로드 가능  

---

## 💡 팁

- 정기적으로 설정을 백업하세요 (data 폴더)
- 마스터링은 "Content ID 회피" 프리셋 권장
- YouTube는 하루에 업로드 제한이 있을 수 있습니다
- 모든 곡은 자동으로 `C:\Users\admin\Desktop\suno` 폴더에서 추적됩니다

---

**시작하기:** `python app.py`를 실행하세요! 🚀

문제가 있으면 언제든지 물어봐도 됩니다! 👍
