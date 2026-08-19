# 🌙 감성힙합 자동화 스튜디오

**배치 설계 → 마스터링 → 커버 이미지 → 메타데이터까지 완벽 자동화**

감성힙합/R&B 음악 제작 워크플로우를 완전히 자동화한 웹앱입니다. Suno AI 기반 음악 생성에서부터 마스터링, 커버 이미지, 메타데이터까지 모든 단계를 한 곳에서 관리할 수 있습니다.

## 🎯 주요 기능

### 1️⃣ 배치 설계 자동화
- **클릭 하나로 10곡 배치 생성**
- 감정별 프리셋 (기본감성, 활력감성, 위로감성, 반성감성)
- 각 곡의 주제, 가사 아웃라인, Suno 스타일 프롬프트 자동 생성
- 마크다운 다운로드로 바로 Suno에 입력 가능

### 2️⃣ 고급 마스터링
- **6단계 마스터링 체인**
  - 소프트 클리핑 (클립핑 방지)
  - 4밴드 멀티밴드 EQ (100Hz, 500Hz, 2kHz, 8kHz)
  - 동적 범위 압축 (3:1 레시오)
  - 스테레오 공간감 강화
  - 제한기 (-1.0dB)
  - LUFS 정규화 (-14.0 LUFS)
- WAV/MP3 파일 업로드 후 자동 처리

### 3️⃣ 커버 이미지 생성
- **감성별 커버 이미지 자동 생성**
- 기본 템플릿 기반 (감성, 활력, 위로, 반성)
- 곡 제목 + 아티스트명 자동 삽입
- 1080x1080 고해상도 PNG 생성

### 4️⃣ 메타데이터 자동화
- 곡 설명 자동 생성
- YouTube 제목/설명 생성
- 태그 & 검색 키워드 자동 생성
- JSON 다운로드 가능

## 🚀 빠른 시작

### 필수 요구사항
- Python 3.8+
- Node.js 16+
- npm

### 백엔드 설정

```bash
# 1. 백엔드 디렉토리로 이동
cd backend

# 2. 가상환경 생성 (선택사항이지만 권장)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 서버 실행
python main.py
```

서버는 `http://localhost:8000`에서 실행됩니다.

### 프론트엔드 설정

```bash
# 1. 프론트엔드 디렉토리로 이동
cd frontend

# 2. 의존성 설치
npm install

# 3. 개발 서버 실행
npm run dev
```

앱은 `http://localhost:3000`에서 실행됩니다.

## 📁 프로젝트 구조

```
.
├── backend/
│   ├── app/
│   │   ├── services/
│   │   │   ├── batch_generator.py     # 배치 설계 자동화
│   │   │   ├── mastering.py           # 고급 마스터링
│   │   │   ├── image_generator.py     # 커버 이미지 생성
│   │   │   └── metadata_generator.py  # 메타데이터 자동화
│   │   └── __init__.py
│   ├── main.py                        # FastAPI 서버
│   ├── requirements.txt
│   └── uploads/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── BatchGenerator.tsx     # 배치 설계 UI
│   │   │   ├── MasteringStudio.tsx    # 마스터링 UI
│   │   │   ├── CoverImageCreator.tsx  # 이미지 생성 UI
│   │   │   └── MetadataEditor.tsx     # 메타데이터 UI
│   │   ├── styles/
│   │   │   └── components.css
│   │   ├── App.tsx                    # 메인 앱
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
└── README.md
```

## 💡 사용 방법

### 배치 설계
1. **배치 설계** 탭 선택
2. 감정 선택 (기본감성/활력감성/위로감성/반성감성)
3. 곡 개수 입력
4. **배치 생성** 클릭
5. 생성된 배치를 마크다운으로 다운로드
6. Suno에서 스타일/가사/제외 항목을 그대로 입력

### 마스터링
1. **마스터링** 탭 선택
2. Suno에서 생성된 MP3/WAV 파일 업로드
3. **마스터링 시작** 클릭 (1~2분 소요)
4. 마스터링된 파일 다운로드

### 커버 이미지
1. **커버 이미지** 탭 선택
2. 곡 제목 입력
3. 아티스트명 입력 (기본값: 새벽공기)
4. 감성 선택
5. **이미지 생성** 클릭
6. PNG 다운로드

### 메타데이터
1. **메타데이터** 탭 선택
2. 곡 제목, 감성, BPM 입력
3. **메타데이터 생성** 클릭
4. YouTube 제목/설명 복사 또는 JSON 다운로드

## 🎨 감성 프리셋

### 기본감성
```
Korean mood hip-hop, R&B hip-hop, singing rap, 
late night city vibe, breathy male vocal, 
restrained emotion, clear diction
```
**분위기**: 밤거리 드라이브, 도시의 외로움, 회상의 순간

### 활력감성
```
Korean mood hip-hop, R&B hip-hop, singing rap, 
confident male vocal, open emotional delivery
```
**분위기**: 새로운 시작, 도시 에너지, 자신감의 순간

### 위로감성
```
Korean mood hip-hop, R&B hip-hop, singing rap, 
warm male vocal, comforting tone
```
**분위기**: 함께라는 것, 작은 위로, 응원의 말

### 반성감성
```
Korean mood hip-hop, R&B hip-hop, singing rap, 
introspective male vocal, vulnerable delivery
```
**분위기**: 지난날 후회, 돌아보는 마음, 깨달음

## 📊 마스터링 스펙

| 항목 | 값 |
|---|---|
| 샘플율 | 44.1kHz |
| 저역 EQ | 100Hz +2dB (Q=0.7) |
| 저중역 EQ | 500Hz +1.5dB (Q=1) |
| 중역 EQ | 2kHz +2dB (Q=1.2) |
| 고역 EQ | 8kHz +1dB (Q=1) |
| 압축 레시오 | 3:1 |
| 압축 임계값 | -20dB |
| 어택/릴리즈 | 10ms / 100ms |
| 제한기 | -1.0dB |
| 타겟 러드니스 | -14.0 LUFS |

## 🔧 API 엔드포인트

### POST `/api/batch/generate`
배치 생성
```json
{
  "mood": "기본감성",
  "count": 10
}
```

### POST `/api/mastering/process`
마스터링 처리 (multipart/form-data)
```
file: Audio file (WAV/MP3)
```

### GET `/api/mastering/download/{file_id}`
마스터링된 파일 다운로드

### POST `/api/image/generate`
커버 이미지 생성
```json
{
  "title": "곡제목",
  "artist": "아티스트",
  "mood": "감성"
}
```

### POST `/api/metadata/generate`
메타데이터 생성
```json
{
  "title": "곡제목",
  "mood": "감성",
  "bpm": 90
}
```

## 📝 라이선스

MIT License

## 🤝 기여

이슈 및 풀 리퀘스트는 언제나 환영합니다!

---

**제작**: 새벽공기 채널  
**최신 업데이트**: 2026년 8월
