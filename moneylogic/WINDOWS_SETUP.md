# 📺 머니로직 파이프라인 - Windows 완벽 가이드

**전체 자동화 영상 생성 및 YouTube 업로드까지 (약 1시간)**

---

## 📋 사전 준비물

- Windows 10/11
- Python 3.10+ 설치
- OpenAI API 키 (https://platform.openai.com/api-keys)
- Google 계정 + YouTube 채널
- PostgreSQL 또는 Docker

---

## 🚀 단계별 설정 (30분)

### 1단계: 저장소 받기

```powershell
# PowerShell에서 실행
cd C:\Users\[username]

# 저장소 클론
git clone https://github.com/1230-png/Soop1230.git
cd Soop1230

# 브랜치 전환
git checkout claude/dazzling-mccarthy-aq4drh

# moneylogic 디렉토리로 이동
cd moneylogic
```

### 2단계: 환경 설정

```powershell
# .env 파일 생성
Copy-Item .env.example .env
```

**메모장으로 `.env` 파일을 열고 수정:**

```env
# === 데이터베이스 ===
DATABASE_URL=postgresql://postgres:password@localhost:5432/moneylogic

# === 환경 ===
ENVIRONMENT=development

# === API 키 ===
OPENAI_API_KEY=sk-...  # ← 여기에 OpenAI 키 붙여넣기

# === YouTube (나중에 설정) ===
# YOUTUBE_CREDENTIALS_JSON=C:\path\to\credentials.json
# YOUTUBE_TOKEN_JSON=C:\path\to\token.json

# === ElevenLabs (선택사항) ===
# ENVIRONMENT=production
# ELEVENLABS_API_KEY=...
# ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB
```

**저장하고 닫기**

### 3단계: PostgreSQL 설정 (선택사항)

**옵션 A: Docker 사용 (권장)**

```powershell
# Docker가 설치되어 있으면
docker run -d `
  -e POSTGRES_PASSWORD=password `
  -e POSTGRES_DB=moneylogic `
  -p 5432:5432 `
  --name moneylogic-db `
  postgres:15
```

**옵션 B: PostgreSQL 설치 (Windows)**

1. https://www.postgresql.org/download/windows/ 에서 다운로드
2. 설치 시 포트 5432, 비밀번호는 "password" 로 설정
3. pgAdmin에서 새 데이터베이스 `moneylogic` 생성

### 4단계: Python 의존성 설치 (10분)

```powershell
# 터미널에서
pip install --upgrade pip

# 의존성 설치 (약 5-10분 소요)
pip install -r requirements.txt

# 설치 확인
python -c "import fastapi, sqlalchemy, openai, edge_tts; print('✅ 모든 의존성 설치됨')"
```

### 5단계: 구조 검증

```powershell
# 전체 구조 검증 (네트워크 불필요)
python test_mock.py
```

**예상 출력:**
```
████████████████████████████████████████████████████████████
█  ✅ 검증 완료!
████████████████████████████████████████████████████████████
```

---

## 🧪 테스트 실행 (15분)

### 테스트 1: 스크립트 생성 (Step 2만)

```powershell
python test_simple.py
```

**예상 결과:**
```
========== 📊 [테스트 1] 금융 데이터 수집 ==========
✅ 데이터 수집 성공!
   현재가: $123.45
   PER: 28.50
   배당수익률: 0.42%

========== 📝 [테스트 2] LLM 스크립트 생성 ==========
✅ 스크립트 생성 성공!
   주제: Apple의 배당금 전략
   세그먼트 수: 5
```

### 테스트 2: 전체 파이프라인 (모든 단계)

```powershell
python test_pipeline.py
```

**처리 과정:**
```
🚀 작업 시작: AAPL (2024-09-05)
📝 스크립트 생성 중...  ✅
🎤 음성 합성 중...       ✅
🎬 영상 렌더링 중...     ✅ (약 2-3분)
📤 YouTube 업로드 중...  (YouTube 자격증명 필요)
✅ 모든 테스트 완료!
```

---

## 🎬 FastAPI 서버 실행 (계속 실행)

새 터미널 창에서:

```powershell
# 서버 시작
python main.py

# 또는
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**성공 표시:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     ✅ 데이터베이스 초기화 완료
```

---

## 📡 API 호출 (영상 생성)

### 방법 1: curl (PowerShell)

```powershell
# 영상 생성 요청
Invoke-WebRequest -Method POST "http://localhost:8000/generate?ticker=AAPL&target_date=2024-09-05"

# 상태 확인 (task_id 확인 후)
Invoke-WebRequest "http://localhost:8000/task/1"
```

### 방법 2: Python 스크립트

```python
import requests

# 영상 생성
response = requests.post("http://localhost:8000/generate", params={
    "ticker": "AAPL",
    "target_date": "2024-09-05"
})

result = response.json()
task_id = result["task_id"]

print(f"작업 시작: {task_id}")

# 상태 조회
import time
time.sleep(5)  # 처리 대기

status = requests.get(f"http://localhost:8000/task/{task_id}").json()
print(f"상태: {status['is_rendered']}")
print(f"영상: {status['video_path']}")
```

### 방법 3: 웹 브라우저 (조회만)

```
http://localhost:8000/health
http://localhost:8000/task/1
```

---

## 📤 YouTube 업로드 설정 (선택사항)

### Step 1: Google OAuth 자격증명 생성

1. Google Cloud Console: https://console.cloud.google.com
2. 새 프로젝트 생성 (이름: "MoneyLogic")
3. API 활성화:
   - YouTube Data API v3 검색 → 활성화
4. OAuth 클라이언트 ID 생성:
   - 좌측 메뉴 → "사용자 인증 정보"
   - "사용자 인증 정보 만들기" → "OAuth 클라이언트 ID"
   - 애플리케이션 유형: "데스크톱 앱"
   - "만들기"
5. JSON 다운로드 → `credentials.json` 저장

### Step 2: .env 업데이트

```env
YOUTUBE_CREDENTIALS_JSON=C:\Users\[username]\Downloads\credentials.json
YOUTUBE_TOKEN_JSON=C:\Users\[username]\moneylogic\token.json
```

### Step 3: 첫 업로드 시 인증

처음 업로드할 때 브라우저 팝업이 뜨면:
1. 구글 계정으로 로그인
2. "YouTube에 업로드" 권한 허용
3. 자동으로 `token.json` 생성

---

## 📊 생성된 파일 위치

```
C:\Users\[username]\moneylogic\
├── test_output/
│   ├── AAPL\2024-09-05\
│   │   ├── segment_000.mp3
│   │   ├── segment_001.mp3
│   │   ├── narration.mp3      ← 최종 오디오
│   │   └── AAPL_2024-09-05.mp4 ← 최종 영상
│   └── video/
│       └── AAPL_2024-09-05.mp4
├── .env                        ← 환경 변수 (비공개)
└── logs/                        (생성되면)
```

---

## 🔧 트러블슈팅

### ❌ "ModuleNotFoundError: No module named 'openai'"

**해결:**
```powershell
pip install openai==1.42.0
```

### ❌ "psycopg2 connection failed"

**해결:**
```powershell
# PostgreSQL 실행 확인
# Windows 서비스에서 "PostgreSQL" 찾아 실행
# 또는 Docker: docker start moneylogic-db
```

### ❌ "OPENAI_API_KEY 환경 변수가 설정되지 않았습니다"

**해결:**
```powershell
# PowerShell에서 확인
$env:OPENAI_API_KEY

# 없으면 .env 파일 다시 확인
cat .env | grep OPENAI
```

### ❌ "moviepy: No such file or directory"

**해결:**
```powershell
pip install imageio-ffmpeg

# 또는 FFmpeg 수동 설치
# https://ffmpeg.org/download.html
```

### ❌ "YouTube upload failed"

**해결:**
```
1. credentials.json이 올바른 경로인지 확인
2. YouTube Data API가 활성화되어 있는지 확인
3. 구글 계정이 YouTube 채널을 소유하고 있는지 확인
```

---

## 📈 성능 최적화

### 빠른 테스트용 설정

```powershell
# 렌더링 품질 낮추기 (빠름)
# app/services/video_renderer.py 수정:
# preset="ultrafast"  # 현재값 (가장 빠름)
# 원하면: "superfast", "veryfast" 등
```

### 프로덕션 설정

```env
ENVIRONMENT=production
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
```

---

## 🚀 일반적인 사용 시나리오

### 시나리오 1: 일회성 영상 생성

```powershell
# 1. 서버 실행
python main.py

# 2. 다른 터미널에서 요청
Invoke-WebRequest -Method POST `
  "http://localhost:8000/generate?ticker=MSFT&target_date=2024-09-10"

# 3. 약 5분 후 YouTube 비공개 영상 자동 업로드됨
```

### 시나리오 2: 매일 자동 생성

Windows Task Scheduler 사용:

```powershell
# 배치 파일 생성: daily_video.bat
python main.py &
powershell -Command "Start-Sleep -Seconds 3600; exit"
```

Task Scheduler에서:
- 트리거: "매일 오전 9시"
- 작업: `daily_video.bat` 실행

---

## ✅ 최종 체크리스트

- [ ] Python 3.10+ 설치됨
- [ ] 저장소 클론 및 브랜치 전환 완료
- [ ] `.env` 파일 생성 및 OPENAI_API_KEY 설정
- [ ] PostgreSQL/Docker 실행 중
- [ ] `pip install -r requirements.txt` 완료
- [ ] `python test_mock.py` 통과
- [ ] `python test_simple.py` 완료
- [ ] `python test_pipeline.py` 완료
- [ ] 영상 파일 생성됨 (`test_output/` 확인)
- [ ] (YouTube 업로드) credentials.json 설정 완료

---

## 📞 추가 지원

### 문서 확인
- `README.md` - 전체 개요
- `.env.example` - 환경 변수 설명
- `app/` - 서비스 코드

### 로그 확인
```powershell
# 상세 로깅
# .env에서: LOG_LEVEL=DEBUG

# 또는 서버 출력 확인
python main.py  # 터미널 메시지 보기
```

### 데이터베이스 확인
```powershell
# PostgreSQL 직접 조회
psql -U postgres -d moneylogic

# SQL: SELECT * FROM video_tasks;
```

---

**🎬 이제 자동 영상 생성의 마법을 경험해보세요! ✨**
