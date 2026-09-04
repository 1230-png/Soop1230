# Windows에서 머니로직 영상 생성 - 완벽 가이드

## 📋 사전 준비 (5분)

### 1. Python 설치 확인
```powershell
python --version
```
> Python 3.10 이상 필요. 없으면 https://www.python.org/downloads/ 에서 설치

### 2. Git 설치 확인
```powershell
git --version
```
> 없으면 https://git-scm.com/download/win 에서 설치

### 3. PostgreSQL 설치 (선택사항)
> Docker 사용 권장 (더 간단함)

---

## 🚀 단계별 설정 (15분)

### Step 1️⃣ : 저장소 받기
```powershell
cd C:\Users\[username]\Desktop
git clone https://github.com/1230-png/Soop1230.git
cd Soop1230\moneylogic
git checkout claude/dazzling-mccarthy-aq4drh
```

### Step 2️⃣ : 환경 설정 (.env 파일 생성)

```powershell
Copy-Item .env.example .env
```

**메모장으로 `.env` 파일 열기** (우클릭 → "편집"):
```env
# === 데이터베이스 ===
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/moneylogic

# === 환경 ===
ENVIRONMENT=development

# === OpenAI API 키 (필수!) ===
OPENAI_API_KEY=sk-...  # ← 여기에 입력!

# === YouTube (나중에 설정) ===
# YOUTUBE_CREDENTIALS_JSON=C:\path\to\credentials.json
# YOUTUBE_TOKEN_JSON=C:\path\to\token.json

# === 로깅 ===
LOG_LEVEL=INFO
OUTPUT_DIR=./test_output
```

**저장 후 닫기** (Ctrl+S)

### Step 3️⃣ : PostgreSQL 실행

#### 옵션 A: Docker 사용 (권장)
```powershell
# Docker가 설치되어 있으면:
docker run -d `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=moneylogic `
  -p 5432:5432 `
  --name moneylogic-db `
  postgres:15
```

#### 옵션 B: PostgreSQL 설치 (Windows)
1. https://www.postgresql.org/download/windows/ 에서 다운로드
2. 설치 시 포트 5432, 비밀번호 "postgres" 로 설정
3. pgAdmin에서 새 데이터베이스 `moneylogic` 생성

### Step 4️⃣ : Python 의존성 설치 (5분)
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

> 설치 확인:
```powershell
python -c "import fastapi, sqlalchemy, openai; print('✅ 준비 완료!')"
```

---

## ✅ 테스트 실행

### Test 1️⃣ : 구조 검증 (네트워크 불필요)
```powershell
python test_mock.py
```

**예상 출력:**
```
████████████████████████████████████████████████████████
█  ✅ 검증 완료!
████████████████████████████████████████████████████████
```

### Test 2️⃣ : 전체 파이프라인 (데모 데이터)
```powershell
python demo_pipeline.py
```

**예상 출력:**
```
🚀 머니로직 파이프라인 - 전체 실행 데모

[Step 1] 데이터베이스 초기화
✅ 데이터베이스 테이블 생성 완료

[Step 2] 테스트 작업 생성
✅ 작업 생성: ID=1, Ticker=DEMO

[Step 3] 스크립트 및 오디오 생성
✅ 오디오 생성: test_output/DEMO/2026-09-05/narration.mp3

[Step 4] 테스트 비디오 생성
✅ 비디오 생성: test_output/DEMO/2026-09-05/DEMO_2026-09-05.mp4

✨ 모든 준비가 완료되었습니다!
```

---

## 🎬 FastAPI 서버 실행

**새로운 PowerShell 창을 열어서:**

```powershell
python main.py
```

**성공하면:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     ✅ 데이터베이스 초기화 완료
```

**웹 브라우저에서 확인:**
```
http://localhost:8000/health
```

**응답:**
```json
{
  "status": "ok",
  "environment": "development",
  "output_dir": "./test_output"
}
```

---

## 📡 API 호출 - 영상 생성

**다른 PowerShell 창에서:**

### 방법 1: PowerShell Invoke-WebRequest (권장)

```powershell
# 영상 생성 요청
$response = Invoke-WebRequest -Method POST `
  "http://localhost:8000/generate?ticker=AAPL&target_date=2024-09-05" `
  -Headers @{"Content-Type"="application/json"}

$result = $response.Content | ConvertFrom-Json
$taskId = $result.task_id

Write-Host "작업 시작: $taskId"
```

### 방법 2: curl 사용

```powershell
# Windows curl:
curl.exe -X POST "http://localhost:8000/generate?ticker=AAPL"
```

### 방법 3: 웹 브라우저 (간단함)

1. 주소창에서:
```
http://localhost:8000/docs
```

2. **"Try it out"** 클릭
3. **"Execute"** 클릭
4. 결과 확인

---

## 📊 작업 상태 확인

```powershell
# PowerShell:
Invoke-WebRequest "http://localhost:8000/task/1" | ConvertFrom-Json | ConvertTo-Json

# 또는 웹 브라우저:
http://localhost:8000/task/1
```

**응답 예시 (처리 중):**
```json
{
  "id": 1,
  "ticker": "AAPL",
  "target_date": "2024-09-05",
  "topic": "Apple의 배당금 전략",
  "is_rendered": false,
  "video_path": null,
  "created_at": "2024-09-05T12:34:56",
  "updated_at": "2024-09-05T12:40:30"
}
```

> `is_rendered: true` 가 될 때까지 반복 확인 (약 5분)

**완료되면:**
```json
{
  "id": 1,
  "ticker": "AAPL",
  "is_rendered": true,
  "video_path": "./test_output/AAPL/AAPL_2024-09-05.mp4",
  ...
}
```

---

## 📤 YouTube 비공개 업로드 설정

### Step 1️⃣ : Google Cloud 자격증명 생성

1. https://console.cloud.google.com 접속
2. 새 프로젝트 생성 (이름: "MoneyLogic")
3. 좌측 메뉴 → **"API 및 서비스"**
4. **"YouTube Data API v3"** 검색 → **활성화**
5. 좌측 메뉴 → **"사용자 인증 정보"**
6. **"사용자 인증 정보 만들기"** → **"OAuth 클라이언트 ID"**
7. 애플리케이션 유형: **"데스크톱 앱"**
8. **"만들기"**
9. **JSON 다운로드** → `credentials.json` 저장

### Step 2️⃣ : .env 파일 업데이트

메모장으로 `.env` 파일 수정:
```env
YOUTUBE_CREDENTIALS_JSON=C:\Users\[username]\Downloads\credentials.json
YOUTUBE_TOKEN_JSON=C:\Users\[username]\moneylogic\token.json
```

**저장 후 서버 재시작** (main.py 재실행)

### Step 3️⃣ : 첫 업로드 시 인증

```powershell
# API 호출
curl.exe -X POST "http://localhost:8000/generate?ticker=AAPL&target_date=2024-09-05"
```

> 처음 업로드할 때 **브라우저 팝업**이 뜸:
> 1. 구글 계정으로 로그인
> 2. **"YouTube에 업로드"** 권한 허용
> 3. 자동으로 `token.json` 생성

**이후 자동으로 YouTube에 비공개 영상 업로드!** 🎉

---

## 🔍 생성된 파일 위치

```
C:\Users\[username]\moneylogic\
├── test_output\
│   ├── AAPL\
│   │   ├── 2024-09-05\
│   │   │   ├── segment_000.mp3
│   │   │   ├── segment_001.mp3
│   │   │   ├── narration.mp3
│   │   │   └── AAPL_2024-09-05.mp4  ← 최종 영상
│   │   └── ...
│   └── ...
├── .env                    ← 환경 변수
├── token.json              ← YouTube 토큰 (자동 생성)
└── logs\                   ← 로그 파일
```

---

## 🆘 문제 해결

### ❌ "ModuleNotFoundError: No module named 'openai'"
```powershell
pip install openai==1.42.0
```

### ❌ "Connection refused" (PostgreSQL)
```powershell
# Docker 재시작
docker restart moneylogic-db

# 또는 Windows 서비스에서 PostgreSQL 실행
```

### ❌ "OPENAI_API_KEY 환경 변수가 설정되지 않았습니다"
```powershell
# .env 파일 다시 확인
Get-Content .env | Select-String OPENAI

# 또는 PowerShell에서 설정:
$env:OPENAI_API_KEY="sk-..."
```

### ❌ "moviepy: No such file or directory"
```powershell
pip install imageio-ffmpeg
# 또는 FFmpeg 수동 설치: https://ffmpeg.org/download.html
```

### ❌ "Port 8000 already in use"
```powershell
# 다른 포트 사용:
# main.py 마지막 줄 수정:
# uvicorn.run(app, host="0.0.0.0", port=8001)
```

---

## 📈 성능 최적화

### 빠른 테스트
```python
# app/services/video_renderer.py 수정:
preset="ultrafast"  # 가장 빠름 (~3분)
```

### 고품질 렌더링
```python
preset="slow"  # 높은 품질 (~10분)
```

---

## 🎯 주요 엔드포인트 정리

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/generate?ticker=AAPL` | POST | 영상 생성 시작 |
| `/task/{id}` | GET | 작업 상태 조회 |
| `/health` | GET | 서버 상태 확인 |
| `/docs` | GET | API 문서 (Swagger UI) |

---

## 💡 팁

### 1️⃣ 여러 종목 동시 생성:
```powershell
curl.exe -X POST "http://localhost:8000/generate?ticker=MSFT"
curl.exe -X POST "http://localhost:8000/generate?ticker=TSLA"
curl.exe -X POST "http://localhost:8000/generate?ticker=NVDA"
```

### 2️⃣ 같은 날짜는 캐싱 (비용 절감):
- 첫 요청: API 호출 ($0.001)
- 두 번째 요청: 즉시 반환 (캐시에서)

### 3️⃣ 로그 확인:
```powershell
Get-Content -Tail 50 logs\*.log
```

### 4️⃣ 백그라운드 실행 (종료하지 않음):
```powershell
# 터미널 창 최소화해두면 백그라운드에서 실행
```

---

## 💰 비용 계산

**1개 영상:**
- yfinance: $0
- OpenAI (gpt-4o-mini, 800 tokens): $0.001
- edge-tts (개발): $0
- YouTube 업로드: $0
- **총: $0.001**

**1개월 (30개 영상): $0.03**

---

## ✨ 완료!

이제 자동으로:
- 📊 재무 데이터 수집
- 📝 OpenAI로 스크립트 생성
- 🎤 TTS로 오디오 합성
- 🎬 moviepy로 영상 렌더링
- 📤 YouTube에 비공개 업로드

가 진행됩니다! 🎬✨

---

## 📚 추가 문서

- **README.md**: 전체 프로젝트 개요
- **COMPLETE_SUMMARY.md**: 완성 보고서
- **WINDOWS_SETUP.md**: 상세 Windows 설정 가이드
