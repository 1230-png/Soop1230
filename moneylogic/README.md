# 머니로직 (MoneyLogic) - 자동화 영상 생성 파이프라인

**완전 자동화된 재무 분석 유튜브 쇼츠 생성 시스템**

- ✅ 금융 데이터 수집 (yfinance)
- ✅ AI 스크립트 생성 (OpenAI gpt-4o-mini)
- ✅ 음성 합성 (edge-tts / ElevenLabs)
- ✅ 영상 렌더링 (moviepy)
- ✅ YouTube 업로드 (비공개)

---

## 🚀 빠른 시작 (5분)

### 1단계: 환경 설정

```bash
cd moneylogic

# .env 파일 생성
cp .env.example .env
```

`.env` 파일 수정:
```env
# 데이터베이스
DATABASE_URL=postgresql://postgres:password@localhost:5432/moneylogic

# 환경
ENVIRONMENT=development  # development 또는 production

# API 키 (필수)
OPENAI_API_KEY=sk-...

# YouTube (선택사항 - 업로드할 때만)
YOUTUBE_CREDENTIALS_JSON=/path/to/credentials.json
YOUTUBE_TOKEN_JSON=/path/to/token.json
```

### 2단계: PostgreSQL 설정

```bash
# PostgreSQL 설치 (Windows의 경우 pgAdmin 사용)
# 또는 Docker:
docker run -d \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=moneylogic \
  -p 5432:5432 \
  postgres:15

# DB 확인
psql -U postgres -d moneylogic -c "SELECT 1;"
```

### 3단계: Python 의존성 설치

```bash
pip install -r requirements.txt
```

### 4단계: 테스트 실행

```bash
# 전체 파이프라인 테스트 (DB 없이)
python test_pipeline.py
```

**예상 결과:**
```
████████████████████████████████████████████████████
█  머니로직 파이프라인 전체 테스트
████████████████████████████████████████████████████

📝 [테스트 1] 스크립트 생성 (yfinance + OpenAI)
✅ 스크립트 생성 성공!
   주제: Apple의 배당금 전략
   총 길이: 45.2초
   세그먼트 수: 5

🎤 [테스트 2] TTS 음성 합성 (edge-tts)
✅ TTS 합성 성공!
   오디오: ./test_output/audio/narration.mp3
   파일 크기: 2.15 MB

🎬 [테스트 3] 영상 렌더링 (moviepy)
✅ 렌더링 완료!
   파일: ./test_output/video/AAPL_2024-09-05.mp4
   크기: 45.30 MB

████████████████████████████████████████████████████
█  ✅ 모든 테스트 완료!
████████████████████████████████████████████████████
```

---

## 🔑 API 자격증명 설정

### OpenAI API 키

1. https://platform.openai.com/api-keys 방문
2. "Create new secret key" 클릭
3. `.env`에 추가:
```env
OPENAI_API_KEY=sk-...
```

### YouTube 업로드 설정 (선택사항)

1. Google Cloud Console: https://console.cloud.google.com
2. 새 프로젝트 생성
3. YouTube Data API v3 활성화
4. OAuth 2.0 클라이언트 ID 생성 (데스크톱 앱)
5. `credentials.json` 다운로드

```env
YOUTUBE_CREDENTIALS_JSON=/absolute/path/to/credentials.json
YOUTUBE_TOKEN_JSON=/absolute/path/to/token.json
```

### ElevenLabs (선택사항, 프로덕션)

1. https://elevenlabs.io/sign-up 회원가입
2. API 키 복사

```env
ENVIRONMENT=production
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB  # "Adam" 목소리
```

---

## 📡 FastAPI 서버 실행

### 개발 모드

```bash
python main.py
# 또는
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### API 요청

#### 영상 생성 요청

```bash
curl -X POST "http://localhost:8000/generate?ticker=AAPL&target_date=2024-09-05"
```

**응답:**
```json
{
  "task_id": 1,
  "ticker": "AAPL",
  "target_date": "2024-09-05",
  "status": "pending",
  "message": "영상 생성이 시작되었습니다"
}
```

#### 작업 상태 조회

```bash
curl "http://localhost:8000/task/1"
```

**응답:**
```json
{
  "id": 1,
  "ticker": "AAPL",
  "target_date": "2024-09-05",
  "topic": "Apple의 배당금 전략",
  "is_rendered": true,
  "video_path": "/path/to/AAPL_2024-09-05.mp4",
  "created_at": "2024-09-05T12:34:56.123456",
  "updated_at": "2024-09-05T12:45:30.654321"
}
```

---

## 🏗️ 프로젝트 구조

```
moneylogic/
├── main.py                      # FastAPI 메인 앱
├── test_pipeline.py             # 테스트 스크립트
├── requirements.txt             # 의존성
├── .env.example                 # 환경 변수 템플릿
├── app/
│   ├── __init__.py
│   ├── config.py               # 설정 (Pydantic)
│   ├── database.py             # SQLAlchemy 설정
│   ├── models.py               # ORM 모델 (VideoTask)
│   ├── repositories.py         # DB 접근 계층
│   ├── services/
│   │   ├── __init__.py
│   │   ├── script_generator.py # Step 2: LLM 스크립트 생성
│   │   ├── tts.py              # Step 3: 환경별 TTS
│   │   ├── video_renderer.py   # Step 4: 영상 렌더링
│   │   └── youtube_uploader.py # Step 5: YouTube 업로드
│   ├── models/
│   ├── schemas/
│   └── services/
└── migrations/                  # Alembic DB 마이그레이션
```

---

## 📊 파이프라인 흐름

```
1. 요청 수신
   POST /generate?ticker=AAPL

2. 캐싱 체크
   DB에서 같은 ticker + date 검색
   → 없으면 새 작업 생성

3. 백그라운드 처리 (_process_video_generation)
   ├─ 금융 데이터 수집 (yfinance)
   ├─ OpenAI 스크립트 생성 (max_tokens=800)
   ├─ TTS 음성 합성 (edge-tts / ElevenLabs)
   ├─ moviepy 영상 렌더링
   ├─ YouTube 업로드 (비공개)
   └─ DB 상태 업데이트

4. 응답 반환
   GET /task/{task_id} → 상태 조회
```

---

## 🔐 보안 체크리스트

- ✅ 모든 API 키는 `.env`에서 로드 (`os.getenv`)
- ✅ `.env` 파일은 `.gitignore`에 추가
- ✅ OpenAI `max_tokens=800` (비용 폭탄 방지)
- ✅ 비동기 처리 (FastAPI BackgroundTasks)
- ✅ DB 캐싱 (중복 API 호출 방지)
- ✅ YouTube 비공개 업로드 (테스트 안전)

---

## 🐛 트러블슈팅

### PostgreSQL 연결 실패

```
ERROR: psycopg2.OperationalError: could not connect to server
```

**해결:**
```bash
# PostgreSQL 실행 확인
psql -U postgres -c "SELECT 1;"

# Windows: pgAdmin 실행
# Linux: sudo systemctl start postgresql
```

### OpenAI API 오류

```
openai.error.AuthenticationError: Incorrect API key provided
```

**해결:**
```bash
# API 키 확인
echo $OPENAI_API_KEY

# .env에서 다시 설정
OPENAI_API_KEY=sk-...
```

### moviepy 렌더링 오류

```
RuntimeError: ImageMagick not found
```

**해결 (Linux):**
```bash
sudo apt-get install -y ffmpeg imagemagick
```

**해결 (Windows):**
- FFmpeg 설치: https://ffmpeg.org/download.html
- 또는 `imageio-ffmpeg` 패키지 재설치

---

## 📈 성능 최적화

| 항목 | 기본값 | 설명 |
|------|-------|------|
| `OPENAI_MAX_TOKENS` | 800 | 비용 절감 |
| `VIDEO_PRESET` | ultrafast | 렌더링 속도 |
| `VIDEO_THREADS` | 4 | CPU 활용도 |
| `POOL_SIZE` | 5 | DB 연결 풀 |

---

## 🎯 다음 단계

- [ ] 스케줄러 추가 (APScheduler)
- [ ] 대량 생성 배치 처리
- [ ] 메트릭 수집 (Prometheus)
- [ ] 에러 알림 (Slack)
- [ ] 웹 대시보드 추가

---

## 📞 문의

문제가 발생하면:
1. `test_pipeline.py` 실행해서 각 단계 확인
2. `.env` 파일 설정 재확인
3. 로그 확인 (`LOG_LEVEL=DEBUG`)

---

**Happy video generation! 🎬**
