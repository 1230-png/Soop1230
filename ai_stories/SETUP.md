# 🎬 AI 스토리텔링 채널 자동화 설정

**목표**: Groq + ElevenLabs + Unsplash + FFmpeg + YouTube API로 **완전 자동화 감성 이야기 채널**

**기능**:
- ✅ AI가 감성 이야기 자동 생성
- ✅ 음성 자동 합성 (ElevenLabs)
- ✅ 배경 이미지 자동 수집 (Unsplash)
- ✅ 영상 자동 제작 (FFmpeg)
- ✅ YouTube 자동 업로드 (OAuth)
- ✅ 매일 2회 자동 실행 (GitHub Actions)

**예상 수익**: 월 100,000 ~ 500,000원 (6개월 후)

---

## 📋 설정 단계

### 1단계: API 토큰 확보 (30분)

#### A. Groq API (AI 이야기 생성)
1. [Groq Console](https://console.groq.com) 방문
2. 회원가입 → API 키 발급
3. `GROQ_API_KEY` 복사

**무료**: 매일 요청 제한 있음 (충분함)

---

#### B. ElevenLabs API (음성 합성)
1. [ElevenLabs](https://elevenlabs.io) 방문
2. 회원가입 → API 키 발급
3. `ELEVENLABS_API_KEY` 복사

**무료**: 100K 글자/월 (매일 3-5개 이야기 가능)

---

#### C. Unsplash API (배경 이미지)
1. [Unsplash Developers](https://unsplash.com/developers) 방문
2. 앱 등록 → `UNSPLASH_ACCESS_KEY` 복사

**무료**: 무제한 (API 제한 50요청/시간)

---

#### D. YouTube OAuth (업로드)

[모바일 환경용 Google API OAuth 토큰 추출](../MOBILE_API_TOKEN_GUIDE.md) 가이드 따르기

필요한 정보:
- `YOUTUBE_REFRESH_TOKEN`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`

---

### 2단계: GitHub Secrets 등록 (15분)

저장소의 **Settings → Secrets and variables → Actions**에서 다음 추가:

```
GROQ_API_KEY = your_groq_api_key
ELEVENLABS_API_KEY = your_elevenlabs_key
UNSPLASH_ACCESS_KEY = your_unsplash_key
YOUTUBE_REFRESH_TOKEN = your_refresh_token
YOUTUBE_CLIENT_ID = your_client_id
YOUTUBE_CLIENT_SECRET = your_client_secret
```

✅ **보안**: 절대 코드에 직접 입력하지 마세요!

---

### 3단계: 채널 생성 (5분)

1. [YouTube Studio](https://studio.youtube.com) 접속
2. **채널 만들기** → 채널명: "감성이야기" 또는 원하는 이름
3. 채널 설명 추가:

```
감성 짧은 이야기 | 일상 속 따뜻한 순간들
매일 새로운 이야기로 힐링하세요 🎬💭
```

4. 썸네일 이미지 설정 (1280x720px)

---

### 4단계: 자동화 테스트 (10분)

#### 수동 테스트 (로컬)
```bash
cd ai_stories

# 이야기 생성 테스트
GROQ_API_KEY=your_key python3 scripts/generate_story.py

# 영상 생성 테스트
GROQ_API_KEY=your_key \
ELEVENLABS_API_KEY=your_key \
UNSPLASH_ACCESS_KEY=your_key \
python3 scripts/generate_story.py | python3 scripts/generate_video.py

# YouTube 업로드 테스트
YOUTUBE_REFRESH_TOKEN=your_token \
YOUTUBE_CLIENT_ID=your_id \
YOUTUBE_CLIENT_SECRET=your_secret \
python3 scripts/generate_story.py | \
python3 scripts/generate_video.py | \
python3 scripts/upload_to_youtube.py
```

#### GitHub Actions 테스트
1. 저장소 **Actions** 탭
2. **AI Stories - 감성 이야기 자동 업로드** 선택
3. **Run workflow** → **Run**
4. 5분 기다리기
5. 로그 확인

---

## ⏰ 자동 실행 일정

현재 설정 (`.github/workflows/ai_stories_daily.yml`):

- **12:00 KST** (UTC 03:00) - 아침 업로드
- **18:00 KST** (UTC 09:00) - 저녁 업로드

**커스터마이즈** (매일 다른 시간):
```yaml
on:
  schedule:
    - cron: '0 6 * * *'   # 15:00 KST
    - cron: '0 12 * * *'  # 21:00 KST
```

---

## 📊 성능 지표

### 초기 (1개월)
- ⏱️ 처리 시간: ~15분/영상
- 📊 생성량: 60개/월
- 💰 수익: 0원 (1,000 구독자 미달)

### 성장 (3개월)
- 📈 구독자: 500 ~ 1,000명
- 🎥 조회수: 5,000 ~ 10,000/월
- 💰 수익: 5,000 ~ 20,000원/월

### 최적화 (6개월)
- 📈 구독자: 2,000 ~ 5,000명
- 🎥 조회수: 50,000 ~ 100,000/월
- 💰 수익: 100,000 ~ 300,000원/월

---

## 🚀 다음 단계

### 즉시 (이번주)
- [ ] API 토큰 모두 확보
- [ ] GitHub Secrets 등록
- [ ] 첫 테스트 실행
- [ ] YouTube 채널 생성

### 1개월 내
- [ ] 자동화 안정화 (실패 시 자동 재시도)
- [ ] 썸네일 자동 생성 추가
- [ ] SEO 최적화 (태그, 제목 개선)
- [ ] 채널 디자인 완성

### 3개월 후
- [ ] 애드센스 신청 (1,000 구독자 달성 후)
- [ ] 추가 채널 생성 (Tier 2)
- [ ] 제휴 마케팅 시작

### 6개월 후
- [ ] 월 100K+ 수익 목표
- [ ] 자동화 파이프라인 완성도 (거의 무인 운영)
- [ ] 여러 채널 다각화

---

## ⚠️ 문제 해결

### "Groq API 에러: 429"
→ 요청 제한 초과. 다음 날 재시도.

### "ElevenLabs: 할당량 초과"
→ 다음 달 대기 또는 유료 업그레이드 ($5/월)

### "Unsplash: 403 Forbidden"
→ API 키 확인 또는 요청 제한 확인

### "YouTube 업로드 실패: 인증 오류"
→ `YOUTUBE_REFRESH_TOKEN` 갱신 필요 (MOBILE_API_TOKEN_GUIDE.md)

### "FFmpeg 명령 실패"
```bash
# 설치 확인
ffmpeg -version
ffprobe -version

# Ubuntu/Debian에서 설치
apt-get install ffmpeg
```

---

## 📈 수익 최대화 팁

### 1. SEO 최적화
- ✅ 제목: "감성 이야기 | [주제]" (20-60자)
- ✅ 설명: 첫 줄 요약 + 타임스탬프 + 제휴 링크
- ✅ 태그: 12~15개 (관련 키워드)

### 2. 썸네일 최적화
- 밝은 색상 + 큰 텍스트
- 구독자 클릭률 목표: 5% 이상
- A/B 테스팅 (다양한 디자인)

### 3. 업로드 시간
- 타겟: 저녁 (18:00~22:00)
- 한국: 18:00 최적
- 글로벌: 자동 다국어 (자막)

### 4. 제휴 마케팅
- 관련 도서/강좌 제휴 링크 삽입
- "이 이야기처럼 힐링하는 [상품]" 추천
- 설명란 맨 아래: `제휴 링크 (수익 배분)`

---

## 💡 추가 아이디어

### 채널 확장
1. **감성 이야기** (현재)
2. **자기계발 팁** (Tier 2)
3. **뉴스 요약** (Tier 2)
4. **ASMR 음악** (Tier 2)

### 수익화 다각화
- 패트론/후원 링크
- 온라인 코스 (udemy)
- 팟캐스트 배포 (Spotify)
- 이메일 뉴스레터

---

## 📞 지원

문제가 있으면:
1. 로그 확인: `.github/workflows/` 실행 기록
2. 이슈 등록: Repository → Issues → New issue
3. 문서 다시 읽기: BLUE_OCEAN_AUTOMATION_ROADMAP.md

---

**마지막 업데이트**: 2026-08-20  
**상태**: 🟢 구성 가능  
**예상 완료**: 1주일
