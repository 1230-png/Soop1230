# [단계 1] PostgreSQL 캐싱 DB 설계 완료

## ✅ 생성된 파일

```
moneylogic/
├── .env.example          # 환경 변수 템플릿 (복사 후 수정 필요)
├── requirements.txt      # 의존성 목록
└── app/
    ├── __init__.py
    ├── config.py         # 설정 관리 (environment 변수 로드)
    ├── database.py       # PostgreSQL async 연결 설정
    ├── models.py         # VideoTask ORM 모델
    ├── models/
    ├── schemas/
    └── services/
```

## 📋 데이터베이스 스키마

### VideoTask 테이블

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | INT | PK (자동증가) |
| `ticker` | VARCHAR(10) | 종목코드 (예: AAPL) |
| `target_date` | VARCHAR(10) | 방송 날짜 (YYYY-MM-DD) |
| `topic` | VARCHAR(255) | 영상 주제 (선택) |
| `script_content` | TEXT | LLM 생성 스크립트 (JSON/마크다운) |
| `audio_path` | VARCHAR(500) | 오디오 파일 경로 |
| `is_rendered` | BOOLEAN | 렌더링 완료 여부 (기본값: false) |
| `video_path` | VARCHAR(500) | 최종 영상 파일 경로 |
| `created_at` | DATETIME | 생성 시간 (UTC) |
| `updated_at` | DATETIME | 수정 시간 (UTC) |

**고유 제약 (Unique Constraint)**
- `ticker + target_date` = **고유** (중복 요청 방지)

**인덱스**
- `ticker`, `target_date` (검색 성능)

## 🚀 로컬 테스트 (Windows)

### 1단계: 환경 설정

```bash
# PowerShell에서 실행
cd C:\Users\admin\moneylogic

# .env 파일 생성 (복사 후 수정)
copy moneylogic\.env.example moneylogic\.env
```

`.env` 수정:
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/moneylogic
ENVIRONMENT=development
OPENAI_API_KEY=sk-... (프로덕션에서만 필요)
LOG_LEVEL=INFO
```

### 2단계: PostgreSQL 데이터베이스 생성

```bash
# PostgreSQL이 로컬에 설치되어 있다고 가정
# psql 명령어로 DB 생성
psql -U postgres -c "CREATE DATABASE moneylogic;"
```

또는 pgAdmin 사용:
- 새 데이터베이스 생성
- 이름: `moneylogic`
- 소유자: postgres

### 3단계: Python 의존성 설치

```bash
# 프로젝트 루트에서
pip install -r moneylogic/requirements.txt
```

### 4단계: 데이터베이스 마이그레이션 (Alembic)

```bash
cd moneylogic

# Alembic 초기화 (첫 실행만)
alembic init migrations

# 마이그레이션 파일 자동 생성
alembic revision --autogenerate -m "Create video_tasks table"

# 마이그레이션 적용
alembic upgrade head
```

### 5단계: 테스트 코드 실행

```bash
# moneylogic 디렉토리에서
python -c "
import asyncio
from app.database import engine, AsyncSessionLocal
from app.models import VideoTask, Base

# DB 테이블 생성
async def setup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('✅ VideoTask 테이블 생성 완료')

asyncio.run(setup())
"
```

**예상 출력:**
```
✅ VideoTask 테이블 생성 완료
```

## 🔍 검증 체크리스트

- [ ] PostgreSQL 데이터베이스 `moneylogic` 생성됨
- [ ] `.env` 파일 생성 (DATABASE_URL 설정)
- [ ] `pip install -r requirements.txt` 성공
- [ ] `python -c "...setup()"` 테스트 성공
- [ ] pgAdmin 또는 psql에서 `video_tasks` 테이블 확인 가능

## 📝 다음 단계

Step 2에서는:
- `yfinance` + `OpenAI API`로 스크립트 생성 함수 작성
- `app/services/script_generator.py` 생성
- 캐싱 로직 구현 (재사용 방지)

**완료 후 여기까지 테스트 완료를 알려주세요!**
