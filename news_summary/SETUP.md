# 🚀 News Summary 채널 설정

**목표**: 매일 최신 뉴스 요약 → Shorts + 분석 영상 자동 생성/업로드

**특징**:
- ✅ 매일 3번 업데이트 (07:00, 12:00, 19:00 KST)
- ✅ 여러 카테고리 동시 처리 (AI, Crypto, Startup)
- ✅ Shorts (30초) + 분석 (3분) 동시 업로드
- ✅ 매우 높은 CPC (금융/기술 분야)
- ✅ 바이럴 가능성 (최신 뉴스 + 빠른 업로드)

**수익 예상**: **가장 높음** (월 500K~1.5M)

---

## 📋 필수 API 토큰 (총 2개)

| API | 무료 한도 | 용도 |
|-----|----------|------|
| **NewsAPI** | 100요청/day | 뉴스 수집 |
| **YouTube** | 무제한 | 업로드 |

### NewsAPI (새로 추가)
1. [NewsAPI.org](https://newsapi.org) 방문
2. 회원가입 → API 키 발급
3. `NEWSAPI_KEY` 복사

**무료**: 100요청/day = 충분함 (하루 15개 기사 × 3 카테고리)

---

## 🛠️ GitHub Secrets 등록

저장소 **Settings → Secrets and variables → Actions**에 추가:

```
NEWSAPI_KEY = [새로 추가]
GROQ_API_KEY = [이미 있음]
ELEVENLABS_API_KEY = [이미 있음] (선택)
YOUTUBE_REFRESH_TOKEN = [이미 있음]
YOUTUBE_CLIENT_ID = [이미 있음]
YOUTUBE_CLIENT_SECRET = [이미 있음]
PEXELS_API_KEY = [이미 있음] (선택)
```

---

## 📰 뉴스 카테고리

현재 설정된 3개 카테고리 (병렬 처리):

### 1️⃣ AI News (가장 높은 CPC)
```
키워드: AI, 머신러닝, GPT, Claude, LLaMA
소스: TechCrunch, The Verge, ArsTechnica
CPC: 매우 높음 ⭐⭐⭐⭐⭐
인기도: 높음 (매일 새로운 소식)
```

### 2️⃣ Crypto News (높은 CPC, 변동성)
```
키워드: 암호화폐, 비트코인, 이더리움, Web3
소스: CoinDesk, Cointelegraph
CPC: 높음 ⭐⭐⭐⭐
인기도: 중간~높음 (시장 변동에 따라)
```

### 3️⃣ Startup News (중간 CPC, 안정적)
```
키워드: 스타트업, VC, IPO, 펀딩
소스: TechCrunch, The Information
CPC: 중간 ⭐⭐⭐
인기도: 중간 (꾸준한 수익)
```

---

## ⏰ 자동 실행 일정

매일 3회:
- **07:00 KST** (UTC 22:00 전날) - 새벽
- **12:00 KST** (UTC 03:00) - 정오
- **19:00 KST** (UTC 10:00) - 저녁

**각 시간마다 3개 카테고리 병렬 처리**
→ 총 일일 최대 **15개 뉴스** (5개/카테고리 × 3회)

---

## 📊 생산량 및 수익 추정

### 월별 영상 수
```
뉴스 기사: 5개/회 × 3회/일 = 15개/일
Shorts: 15개/일 × 30일 = 450개/월
분석: 15개/일 × 30일 = 450개/월
합계: 900개/월 (growth_tips 600개 + 300개)
```

### 예상 수익 (6개월)

| 항목 | 월 1-2 | 월 3 | 월 4 | 월 5 | 월 6 |
|------|--------|------|------|------|------|
| 구독자 | 100 | 500 | 1.5K | 3K | 5K |
| 조회수 | 3K | 20K | 100K | 300K | 1M |
| 수익 | 0 | 5K | 50K | 150K | 500K |

---

## 🔧 수동 테스트

```bash
cd news_summary

# 1. 뉴스 수집 (AI 카테고리)
NEWSAPI_KEY=your_key python3 scripts/fetch_news.py ai 3

# 2. 한국어 요약 생성
NEWSAPI_KEY=your_key \
GROQ_API_KEY=your_key \
python3 scripts/fetch_news.py ai 2 | \
python3 scripts/generate_summary.py

# 3. 영상 생성
NEWSAPI_KEY=your_key \
GROQ_API_KEY=your_key \
python3 scripts/fetch_news.py ai 1 | \
python3 scripts/generate_summary.py | \
python3 scripts/generate_video.py

# 4. YouTube 업로드
NEWSAPI_KEY=your_key \
GROQ_API_KEY=your_key \
YOUTUBE_REFRESH_TOKEN=your_token \
YOUTUBE_CLIENT_ID=your_id \
YOUTUBE_CLIENT_SECRET=your_secret \
python3 scripts/fetch_news.py ai 1 | \
python3 scripts/generate_summary.py | \
python3 scripts/generate_video.py | \
python3 scripts/upload_news.py
```

---

## 💰 수익 모델

### 1. 애드센스 (높은 CPC)
- 기술/금융 콘텐츠: CPC $5~20
- 평균 RPM (1000 조회당): $20~50
- 예상: 월 100조회 → $2~5K

### 2. 제휴 마케팅
- 암호화폐 거래소 (Upbit, Coinbase)
- 자산 관리 앱 (라임, 토스)
- 기술 서적/강좌

### 3. 후원/Patreon
- 상세 분석 콘텐츠 구독 모델
- 뉴스레터 (이메일)

---

## 🎯 경쟁 우위

### 왜 News Summary가 특별한가?

1. **매우 높은 CPC**
   - 일반 채널: $1~3 CPC
   - 기술 채널: $5~10 CPC
   - 뉴스 채널: **$10~30 CPC** ⭐

2. **바이럴 가능성**
   - 최신 뉴스는 검색 트래픽 높음
   - YouTube 추천 알고리즘에 유리
   - 구독자 빠른 성장

3. **제휴 기회**
   - 금융/암호화폐 업체 스폰서
   - 높은 직거래 수수료

4. **확장성**
   - 카테고리 추가 쉬움 (설정만 변경)
   - 여러 채널 운영 가능
   - (예: ai_news, crypto_news, startup_news 별개 채널)

---

## ⚠️ 주의사항

### NewsAPI 할당량
```
무료: 100요청/day
현재 사용: 15요청/day (충분함)

추가하면:
4개 카테고리: 20요청/day (여전히 안전함)
```

### 정확성
- 원본 링크를 항상 포함 (신뢰성)
- Groq 요약이 100% 정확하지 않을 수 있음
- 설명란에 "AI 요약"임을 명시

### 저작권
- 뉴스 헤드라인은 자유로움 (Fair Use)
- 하지만 전체 기사 내용은 포함하지 않음
- 원본 링크 제공으로 보완

---

## 📈 성장 전략

### Phase 1: 기초 다지기 (월 1-2)
- ✅ 뉴스 채널 안정화
- ✅ 1개 카테고리 집중 (AI)
- ✅ 구독자 모음 (100~300)

### Phase 2: 다각화 (월 3-4)
- ✅ 3개 카테고리 모두 활성화
- ✅ 별개 채널 생각 (crypto_news, startup_news)
- ✅ 구독자 1K+ 달성

### Phase 3: 수익화 (월 5-6)
- ✅ 애드센스 승인 및 수익
- ✅ 제휴 계약 체결
- ✅ 월 500K+ 수익

### Phase 4: 스케일 (월 7+)
- ✅ 새로운 카테고리 추가 (Tech, Finance)
- ✅ 뉴스레터 시작 (이메일 리스트 수집)
- ✅ 팟캐스트 배포 (Spotify)

---

## 🔄 커스터마이즈

### 카테고리 추가하기

`fetch_news.py`의 `NEWS_CATEGORIES`에 추가:

```python
"finance": {
    "keywords": "stock OR bonds OR market OR economics",
    "sources": "cnbc,bloomberg",
    "language": "en",
    "description": "Finance News",
},
```

그 후 워크플로우의 `matrix.category`에 추가:

```yaml
matrix:
  category: [ai, crypto, startup, finance]
```

### 업로드 빈도 변경

워크플로우의 `cron`을 수정:

```yaml
schedule:
  - cron: '0 9 * * *'   # 새 시간 추가
  - cron: '0 15 * * *'  # 새 시간 추가
```

---

## 📚 다음 단계

### 즉시 (오늘)
- [ ] NewsAPI 키 발급
- [ ] GitHub Secrets 등록
- [ ] 첫 번째 테스트 실행

### 1주일
- [ ] 매일 자동 업로드 확인
- [ ] 조회수 모니터링
- [ ] 인기 카테고리 분석

### 1개월
- [ ] 구독자 300+ 달성
- [ ] 카테고리별 성과 분석
- [ ] 새로운 카테고리 추가 계획

### 3개월
- [ ] 구독자 1K+ → 애드센스 신청
- [ ] 제휴사 컨택
- [ ] 별개 채널 시작 (예: crypto_news)

---

## 📊 다른 채널과의 비교

| 항목 | AI Stories | Growth Tips | News Summary |
|------|-----------|------------|-------------|
| **매일 영상** | 2개 | 10개 | 15개 |
| **월 영상** | 60개 | 600개 | 450개 |
| **CPC** | 중간 | 높음 | **매우 높음** ⭐⭐⭐⭐⭐ |
| **6개월 수익** | 100K~300K | 300K~900K | **500K~1.5M** |

---

## 💡 팁

### SEO 최적화
- 제목: "[카테고리] 뉴스 요약" + 주요 키워드
- 설명: 원본 링크 + 해시태그
- 태그: 뉴스 + 카테고리 + 회사명

### 썸네일 최적화
- 카테고리별 색상 (AI: 파란색, Crypto: 주황색)
- 큰 텍스트 (제목 요약)
- 카테고리 태그 (#AI, #CRYPTO)

### 제목 패턴
```
[AI] GPT-5 발표, 업계 충격
[CRYPTO] 비트코인 $50K 돌파
[STARTUP] OpenAI Series X 투자 유치
```

---

**상태**: 🟢 구성 가능  
**예상 완료**: 1-2주  
**ROI**: **최고 수준** (매우 높은 CPC)  
**추천**: **필수 구현** (AI Stories/Growth Tips와 시너지)
