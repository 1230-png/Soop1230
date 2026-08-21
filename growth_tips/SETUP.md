# 🚀 Growth Tips 채널 설정

**목표**: 매일 10개의 자기계발 Shorts 자동 생성 + 업로드

**특징**:
- ✅ 매일 10개 (ai_stories 2개보다 5배 많음)
- ✅ 45초 Shorts (빠른 조회수)
- ✅ 이중언어 (한국어/영어)
- ✅ 높은 CPC (교육용 콘텐츠)
- ✅ 완전 무료

**수익 예상**: ai_stories보다 **2-3배 높음** (같은 기간)

---

## 📋 필수 API 토큰

| API | 무료 한도 | 용도 |
|-----|----------|------|
| **Groq** | 무제한 (요청 제한) | 팁 생성 |
| **Pexels** | 무제한 | 배경 영상 |
| **YouTube** | 무제한 | 업로드 |

**Pexels API (새로 추가)**:
1. [Pexels Developers](https://www.pexels.com/developers/) 방문
2. 회원가입 → API 키 발급
3. `PEXELS_API_KEY` 복사

---

## 🛠️ GitHub Secrets 등록

저장소 **Settings → Secrets and variables → Actions**에 추가:

```
GROQ_API_KEY = [이미 있음]
PEXELS_API_KEY = [새로 추가]
YOUTUBE_REFRESH_TOKEN = [이미 있음]
YOUTUBE_CLIENT_ID = [이미 있음]
YOUTUBE_CLIENT_SECRET = [이미 있음]
```

---

## ⏰ 자동 실행 일정

매일:
- **10:00 KST** (UTC 01:00) - 10개 업로드 (아침)
- **20:00 KST** (UTC 11:00) - 10개 업로드 (저녁)

**총 매일 20개 Shorts** 🔥

---

## 📊 ai_stories vs growth_tips 비교

| 항목 | AI Stories | Growth Tips |
|------|-----------|------------|
| **매일 개수** | 2개 | 10개 |
| **길이** | 3-5분 | 45초 |
| **음성** | 있음 (비용) | 없음 (텍스트) |
| **생성 시간** | ~15분 | ~10분 |
| **CPC** | 보통 | 높음 (교육) |
| **월 영상** | 60개 | 600개 |
| **6개월 예상 수익** | 100K~300K | **300K~900K** |

---

## 🎯 팁 카테고리

자동으로 생성되는 팁:

1. **생산성** - 시간 활용, 집중력, 멀티태스킹
2. **습관 형성** - 루틴, 목표 달성, 자기관리
3. **심리학** - 동기부여, 자신감, 스트레스 관리
4. **금융** - 저축, 투자, 재정 계획
5. **커리어** - 능력 개발, 인맥, 경력 관리
6. **시간 관리** - 우선순위, 계획, 실행
7. **자신감** - 긍정 사고, 실패 극복
8. **동기부여** - 목표 설정, 성공 습관
9. **의사소통** - 리더십, 설득, 협력
10. **학습** - 공부 방법, 기억력, 이해도

매일 10개를 모두 생성하므로, **다양한 주제 커버 가능**.

---

## 🔧 수동 실행 (테스트)

```bash
cd growth_tips

# 팁 생성 테스트
GROQ_API_KEY=your_key python3 scripts/generate_tips.py 3

# Shorts 생성 테스트
GROQ_API_KEY=your_key \
PEXELS_API_KEY=your_key \
python3 scripts/generate_tips.py 3 | python3 scripts/generate_shorts.py

# YouTube 업로드 테스트
GROQ_API_KEY=your_key \
PEXELS_API_KEY=your_key \
YOUTUBE_REFRESH_TOKEN=your_token \
YOUTUBE_CLIENT_ID=your_id \
YOUTUBE_CLIENT_SECRET=your_secret \
python3 scripts/generate_tips.py 2 | \
python3 scripts/generate_shorts.py | \
python3 scripts/upload_shorts.py
```

---

## 💰 수익 전망

### 초기 (1개월)
- 📊 영상: 600개
- 👥 구독자: 300-500명
- 💰 수익: 0원

### 성장 (3개월)
- 👥 구독자: 2,000-3,000명
- 📊 조회수: 50,000~100,000/월
- 💰 수익: 30,000~80,000원/월

### 최적화 (6개월)
- 👥 구독자: 5,000~10,000명
- 📊 조회수: 500,000~1,000,000/월
- 💰 수익: **300,000~900,000원/월** ⭐

---

## ⚠️ 문제 해결

### "Pexels: 429 Too Many Requests"
→ API 요청 제한 (50/시간)
→ 다시 실행하면 자동 복구

### "FFmpeg 에러: drawtext 실패"
→ 한글 폰트 미설치
```bash
apt-get install fonts-noto-cjk
```

### "배경 영상 다운로드 실패"
→ 폴백 사용 (단색 배경으로 자동 생성)

### "YouTube 업로드가 느림"
→ 정상 (네트워크 대역폭)
→ 일괄 업로드는 한 번에 10개까지

---

## ✨ 최적화 팁

### 1. 썸네일 자동 생성
현재: 자동 생성 안 함 (YouTube 기본)
향후: PIL로 예쁜 썸네일 추가

### 2. 해시태그 최적화
현재: 기본 태그만 사용
향후: 주제별 해시태그 자동 생성

### 3. 크로스 플랫폼
현재: YouTube만
향후: TikTok, Instagram Reels도 가능

### 4. 제휴 링크
현재: 설명란 기본만
향후: 자동으로 제휴 링크 삽입
예: "이 팁 관련 온라인 코스 [제휴 링크]"

---

## 🎬 다음 단계

### 즉시 (오늘)
- [ ] Pexels API 토큰 확보
- [ ] GitHub Secrets에 등록
- [ ] 첫 번째 자동화 테스트

### 1주일
- [ ] 매일 10개 업로드 확인
- [ ] 조회수 모니터링
- [ ] 인기 팁 분석

### 1개월
- [ ] 구독자 300+ 달성
- [ ] 성과 분석 및 개선
- [ ] 새로운 카테고리 추가 (옵션)

### 3개월
- [ ] 애드센스 신청 (1K 구독자 필요)
- [ ] 제휴 마케팅 시작
- [ ] Tier 2 채널 추가 (뉴스 요약)

---

## 📈 성공 사례 시뮬레이션

```
Day 1:   영상 20개 업로드 (첫 날)
Week 1:  140개 영상, 200 조회, 5 구독자
Week 2:  280개 영상, 800 조회, 15 구독자
Week 3:  420개 영상, 3K 조회, 40 구독자
Month 1: 600개 영상, 15K 조회, 100 구독자 ✅

Month 2: 1,200개 영상, 80K 조회, 500 구독자
Month 3: 1,800개 영상, 200K 조회, 1,000 구독자 ✅ 애드센스 신청

Month 4: 2,400개 영상, 500K 조회, 2,000 구독자
Month 5: 3,000개 영상, 1M 조회, 3,500 구독자
Month 6: 3,600개 영상, 2M 조회, 5,000 구독자 🎉

예상 수익: $500 ~ $2,000/월 (약 650K ~ 2.6M원)
```

---

## 🆚 AI Stories와 병렬 운영

| 채널 | 일일 영상 | 길이 | 누적 효과 |
|------|----------|------|---------|
| ai_stories | 2개 | 3-5분 | 콘텐츠 다양성 |
| growth_tips | 10개 | 45초 | 브랜드 인지도 |
| **합계** | **12개** | **다양** | **시너지** |

**장점**:
- 채널 다각화 (리스크 분산)
- 더 많은 구독자 노출
- 서로 다른 수익원 (애드센스 + 제휴)
- 같은 토큰으로 2배 수익

---

## 📚 참고

- [QUICK_START.md](../QUICK_START.md) - 빠른 시작
- [BLUE_OCEAN_AUTOMATION_ROADMAP.md](../BLUE_OCEAN_AUTOMATION_ROADMAP.md) - 전체 전략
- [Pexels API Docs](https://www.pexels.com/api/documentation/)

---

**상태**: 🟢 구성 가능  
**예상 완료**: 1-2주  
**ROI**: **매우 높음** (음성 API 비용 없음)
