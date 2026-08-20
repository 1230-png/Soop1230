# ⚡ 빠른 시작 가이드 (5분)

## 🎯 당신의 최종 목표

```
✅ 아무것도 하지 않아도
✅ 컴퓨터를 켜지 않아도  
✅ 매일 자동으로
✅ YouTube에 영상이 올라가고
✅ 월 100,000원 이상 벌기
```

**이 가이드**: 그것을 구현하는 **가장 빠른 길**

---

## 🚀 5단계 (4시간)

### Step 1️⃣: API 토큰 4개 확보 (30분)

| API | 링크 | 복사할 값 |
|-----|------|---------|
| **Groq** | https://console.groq.com | `GROQ_API_KEY` |
| **ElevenLabs** | https://elevenlabs.io/settings/api-keys | `ELEVENLABS_API_KEY` |
| **Unsplash** | https://unsplash.com/developers | `UNSPLASH_ACCESS_KEY` |
| **YouTube OAuth** | [가이드](./MOBILE_API_TOKEN_GUIDE.md) | `YOUTUBE_REFRESH_TOKEN` |

모두 **무료**입니다. 회원가입만 하면 끝.

---

### Step 2️⃣: GitHub Secrets에 등록 (5분)

저장소 → **Settings** → **Secrets and variables** → **Actions**

다음 6개 추가:
```
GROQ_API_KEY = [복사한 값]
ELEVENLABS_API_KEY = [복사한 값]
UNSPLASH_ACCESS_KEY = [복사한 값]
YOUTUBE_REFRESH_TOKEN = [복사한 값]
YOUTUBE_CLIENT_ID = [복사한 값]
YOUTUBE_CLIENT_SECRET = [복사한 값]
```

✅ **Secrets은 코드에 안 보임** (GitHub가 암호화)

---

### Step 3️⃣: YouTube 채널 생성 (5분)

1. [YouTube Studio](https://studio.youtube.com) 열기
2. "채널 만들기" 클릭
3. 채널명: "감성이야기" (또는 원하는 이름)
4. 설명 추가:
   ```
   감성 짧은 이야기 | 일상 속 따뜻한 순간들
   매일 자동 업로드 🎬💭
   ```

---

### Step 4️⃣: 첫 번째 자동화 테스트 실행 (20분)

1. 이 저장소 → **Actions** 탭
2. **"AI Stories - 감성 이야기 자동 업로드"** 선택
3. **"Run workflow"** → **"Run"** 클릭
4. ⏳ 15분 기다리기

**결과**:
- ✅ YouTube 채널에 영상 1개 올라옴
- ✅ 내일 같은 시간에 자동으로 또 올라옴

---

### Step 5️⃣: 매일 자동 실행 확인 (확인만)

workflow 설정이 이미 되어있음:
- **매일 12:00 KST** - 자동 실행
- **매일 18:00 KST** - 자동 실행

더 이상 할 일 없음. **그냥 기다리면 됨.**

---

## 💰 수익 타임라인

```
Month 1  → 0원 (구축 기간, 구독자 모음)
Month 2  → 100 구독자
Month 3  → 1,000 구독자 → ✅ 애드센스 신청 가능
Month 4  → 애드센스 첫 수익 (5,000~20,000원)
Month 5  → 30,000~50,000원
Month 6  → 100,000~300,000원 ⭐
Month 12 → 500,000~1,000,000원+
```

**핵심**: 처음 3개월은 "구축 기간". 인내심이 필요.

---

## 📚 추가 채널 추가하기 (선택)

1개 채널이 자동화되면, 쉽게 2번째 채널 추가 가능:

### 추가 가능한 채널 (블루 오션)

```
1. 자기계발 팁 (Shorts) ← 높은 CPC
2. 뉴스 요약 (암호화폐/AI) ← 매우 높은 CPC  
3. ASMR 음악 (로피파이) ← 스트리밍 수익
4. 제품 리뷰 (제휴 수익) ← 아마존/쿠팡
5. 교육 콘텐츠 (프로그래밍) ← 온라인코스 제휴
```

자세한 내용: [BLUE_OCEAN_AUTOMATION_ROADMAP.md](./BLUE_OCEAN_AUTOMATION_ROADMAP.md)

---

## ❌ 흔한 실패

### "GitHub Actions 실행이 빨간색 (실패함)"
→ **Secrets 값이 빠졌거나 잘못됨**
- Settings → Secrets에서 다시 확인
- API 키가 정확한지 확인

### "YouTube 업로드 안 됨"
→ **YouTube 채널이 없거나, OAuth 토큰이 잘못됨**
- YouTube Studio에서 채널 확인
- MOBILE_API_TOKEN_GUIDE.md로 토큰 재생성

### "영상이 검은 화면"
→ **배경 이미지를 못 찾음** (네트워크 문제)
- Unsplash API 키 확인
- 다시 실행 (자동 재시도 기능)

---

## 🆘 더 도움 필요?

### 문서
- 📖 [블루 오션 전전략](./BLUE_OCEAN_AUTOMATION_ROADMAP.md) - 상세 가이드
- 🔐 [YouTube OAuth 가이드](./MOBILE_API_TOKEN_GUIDE.md) - 토큰 추출
- 📝 [AI Stories 설정](./ai_stories/SETUP.md) - 채널별 세부 설정

### GitHub Issues
문제 발생 시:
1. Repository → **Issues** → **New issue**
2. "Github Actions 실패" 선택
3. 로그 스크린샷 올리기
4. 설명하기

---

## ✨ 가장 중요한 2가지

### 1️⃣ 처음 2주는 포기하지 말 것
- 구독자 0명 (당연함, 모두가 그럼)
- 수익 0원 (당연함, 1K 구독자까지)
- **계속 업로드하는 것이 유일한 성공 공식**

### 2️⃣ 3개월 후부터 수익화
- 구독자 1,000명 → 애드센스 신청
- 구독자 5,000명 → 스폰서 도청
- 구독자 10,000명 → 제휴사 거래

---

## 🎬 지금 바로 시작

```bash
# 이미 이 저장소가 준비되어 있음
# 이제 하면 될 일:

1. API 토큰 4개 확보 (30분)
   ↓
2. GitHub Secrets에 등록 (5분)
   ↓
3. YouTube 채널 생성 (5분)
   ↓
4. GitHub Actions 테스트 실행 (20분)
   ↓
5. 매일 자동으로 올라옴 🎉

시간: 총 65분
비용: 0원
결과: 월 100K+ 수익 (6개월 후)
```

---

## 📊 진행 상황 추적

완료한 항목에 ✅ 표시:

- [ ] Groq API 토큰 확보
- [ ] ElevenLabs API 토큰 확보
- [ ] Unsplash API 토큰 확보
- [ ] YouTube OAuth 토큰 확보 (가장 오래 걸림)
- [ ] GitHub Secrets에 모두 등록
- [ ] YouTube 채널 생성
- [ ] 첫 번째 GitHub Actions 실행
- [ ] 첫 번째 영상 확인
- [ ] 다음날 자동 업로드 확인
- [ ] 1주일 후 구독자 확인
- [ ] 1개월 후 추가 채널 생성

---

## 🎯 최종 확인

이 체크리스트를 모두 완료하면:

✅ 완전 자동화  
✅ 무료 (0원)  
✅ 매일 업로드 (수동 개입 X)  
✅ 24/7 무중단 운영  
✅ 수익화 중심  

**축하합니다! 당신의 자동 수익 기계가 완성됐습니다.** 🚀

---

**다음 단계**: [BLUE_OCEAN_AUTOMATION_ROADMAP.md](./BLUE_OCEAN_AUTOMATION_ROADMAP.md)로 추가 채널 계획

**질문?** GitHub Issues에 작성하세요  
**성공했어?** 이 Repo에 ⭐ 주세요!
