# 🍳 음식 쇼츠 채널 자동화 — 설정 가이드 (전부 무료)

**채널 포맷**: 간단한 요리 + 음식 리뷰 + 주방용품 소개 → 30초 수직 쇼츠  
**자동화**: 하루 2-3편 자동 생성 & 업로드 (쿠팡 파트너스 링크 자동 삽입)  
**수익화**: 유튜브 애드센스 + 쿠팡 파트너스 커미션

이 문서의 설정을 완료하면, GitHub Actions이 매일 자동으로:
1. 음식 콘텐츠 생성 (영상 + 음성)
2. 쿠팡 상품 자동 매칭
3. YouTube에 업로드 & 쿠팡 링크 삽입
4. 기록 저장

**비용**: 0원 (모든 서비스 무료 계층)

---

## 1️⃣ YouTube 채널 준비

### 1-1. 새 YouTube 계정 생성 (선택사항)
- 기존 계정이 있으면 그 계정 사용 가능
- 음식 채널용 새 계정을 원하면: [youtube.com](https://youtube.com) 방문 → 프로필 생성

### 1-2. 채널 커스터마이즈
- YouTube Studio 로그인
- **채널 커스터마이즈**
  - 프로필 사진: 음식 아이콘 또는 로고
  - 배너: 음식/요리 테마
  - 채널 설명: "맛있는 요리와 음식 리뷰"

---

## 2️⃣ Google Cloud 설정 (YouTube API)

### 2-1. Google Cloud 프로젝트 생성
1. https://console.cloud.google.com 방문
2. **새 프로젝트** 클릭
3. 프로젝트 이름: `food-shorts-automation` (또는 원하는 이름)
4. **만들기** 클릭

### 2-2. YouTube Data API v3 활성화
1. 좌측 메뉴: **API 및 서비스** → **라이브러리**
2. "YouTube Data API v3" 검색
3. **사용 설정** 클릭

### 2-3. OAuth 동의 화면 설정
1. **API 및 서비스** → **OAuth 동의 화면**
2. **User Type**: 외부(External) 선택
3. **기본 정보** 입력:
   - 앱 이름: `Food Shorts Automation`
   - 지원 이메일: 본인 이메일
   - 개발자 연락처: 본인 이메일
4. **게시 상태**: "테스트 중" (괜찮음)
5. **테스트 사용자 추가**:
   - 음식 채널을 관리할 Google 계정 이메일 추가
6. **저장 후 계속**

### 2-4. OAuth 클라이언트 ID 생성
1. **API 및 서비스** → **사용자 인증 정보**
2. **사용자 인증 정보 만들기** → **OAuth 클라이언트 ID**
3. **애플리케이션 유형**: 데스크톱 앱
4. **만들기** 클릭
5. **JSON 다운로드** 클릭 → `client_secret.json` 저장

---

## 3️⃣ Refresh Token 발급

### 3-1. 로컬에서 한 번만 실행

```bash
cd channel_food/scripts
pip install google-auth-oauthlib
python3 get_refresh_token.py --client-secret /path/to/client_secret.json
```

### 3-2. 결과 저장
터미널에 아래처럼 출력됩니다:

```
client_id:     xxxxxxxxxxxxxxxx.apps.googleusercontent.com
client_secret: xxxxxxxxxxxxxxxx
refresh_token: 1//xxxxxxxxxxxxxxxxxxxxxxxx
```

**이 값들을 복사해두세요!** (다음 단계에서 필요)

---

## 4️⃣ GitHub Secrets 등록

### 4-1. 저장소 설정으로 이동
1. GitHub: `1230-png/Soop1230` 저장소
2. **Settings** → **Secrets and variables** → **Actions**
3. **New repository secret** 클릭

### 4-2. 3개의 Secret 추가

| Secret 이름 | 값 (3-2에서 복사) |
|---|---|
| `YT_CLIENT_ID` | `xxxxxxxxxxxxxxxx.apps.googleusercontent.com` |
| `YT_CLIENT_SECRET` | `xxxxxxxxxxxxxxxx` |
| `YT_REFRESH_TOKEN` | `1//xxxxxxxxxxxxxxxxxxxxxxxx` |

---

## 5️⃣ 쿠팡 파트너스 설정 (선택사항)

### 5-1. 쿠팡 파트너스 가입
1. https://partners.coupang.com 방문
2. **회원가입** → 일반 회원으로 가입
3. **파트너스 신청** → 승인 대기 (보통 24시간)

### 5-2. 아이디 & 태그 받기
- 승인 후, 파트너스 대시보드에서 **아이디** 및 **캠페인 태그** 확인
- 상품 링크 생성 방법:
  ```
  https://www.coupang.com/vp/products/상품ID?&campaignId=YOUR_CAMPAIGN_ID
  ```

### 5-3. 링크 등록
- `scripts/coupang_products.json`의 `link` 필드에 실제 쿠팡 파트너스 링크 입력

**예시:**
```json
{
  "name": "무항생제 계란",
  "link": "https://www.coupang.com/vp/products/1234567890?&campaignId=YOUR_CAMPAIGN_ID",
  "keywords": ["계란", "계란요리"]
}
```

---

## 6️⃣ 콘텐츠 커스터마이즈

### 6-1. 음식 콘텐츠 추가
`scripts/food_content.json`에 새로운 항목 추가:

```json
{
  "id": 9,
  "type": "recipe",
  "title": "5분 계란후라이",
  "description": "완벽한 반숙 계란후라이 만드는 법",
  "korean": "계란후라이",
  "English": "Fried egg",
  "ingredients": ["계란", "소금", "버터"],
  "coupang_keywords": ["계란", "팬"],
  "duration_sec": 30,
  "hashtags": ["#계란", "#프라이", "#간단요리"]
}
```

### 6-2. 쿠팡 상품 추가
`scripts/coupang_products.json`에 상품 추가:

```json
{
  "name": "고급 올리브유",
  "link": "https://www.coupang.com/vp/products/...",
  "keywords": ["요리", "기름", "올리브"]
}
```

---

## 7️⃣ 수동 테스트 (첫 영상)

### 7-1. 로컬에서 영상 생성
```bash
cd channel_food/scripts
python3 generate_food_video.py
```

**출력:**
```
[생성] recipe: 1분 계란말이 만드는 법
[상품] 2개 매칭됨
[완료] /home/user/Soop1230/channel_food/output/food_shorts_1.mp4
```

### 7-2. 업로드
```bash
python3 upload_food_video.py \
  --video-path channel_food/output/food_shorts_1.mp4 \
  --metadata-path channel_food/output/metadata_1.json \
  --privacy-status unlisted
```

✅ 성공하면: `https://youtube.com/watch?v=xxxxx` 링크 출력

---

## 8️⃣ GitHub Actions 자동화

### 8-1. 워크플로우 파일 생성
`.github/workflows/food_shorts_publish.yml` 생성:

```yaml
name: 음식 쇼츠 자동 생성 & 업로드

on:
  schedule:
    - cron: '0 9,15,21 * * *'  # 매일 09:00, 15:00, 21:00 (KST 기준)
  workflow_dispatch:

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Python 설정
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: 의존성 설치
        run: |
          cd channel_food/scripts
          pip install -r requirements.txt
      
      - name: 영상 생성
        run: |
          cd channel_food/scripts
          python3 generate_food_video.py > result.json
      
      - name: 유튜브 업로드
        env:
          YT_CLIENT_ID: ${{ secrets.YT_CLIENT_ID }}
          YT_CLIENT_SECRET: ${{ secrets.YT_CLIENT_SECRET }}
          YT_REFRESH_TOKEN: ${{ secrets.YT_REFRESH_TOKEN }}
        run: |
          cd channel_food/scripts
          RESULT=$(cat result.json | python3 -c "import sys, json; r=json.load(sys.stdin); print(f\"{r['video_path']} {r['metadata_path']}\")")
          python3 upload_food_video.py \
            --video-path $(echo $RESULT | cut -d' ' -f1) \
            --metadata-path $(echo $RESULT | cut -d' ' -f2) \
            --privacy-status public
      
      - name: 변경사항 커밋
        run: |
          git config user.email "action@github.com"
          git config user.name "GitHub Action"
          git add channel_food/used_log.csv
          git commit -m "📹 자동 생성 음식 쇼츠 기록" || true
          git push
```

### 8-2. 설정
1. 위 내용을 `.github/workflows/food_shorts_publish.yml`로 저장
2. Git commit & push
3. GitHub Actions 탭에서 "음식 쇼츠 자동 생성 & 업로드" 워크플로우 확인

---

## 💡 팁 & 트러블슈팅

### 영상 생성 실패?
```bash
# 폰트 설치
sudo apt-get install -y fonts-noto-cjk

# ffmpeg 설치
sudo apt-get install -y ffmpeg
```

### 쿠팡 링크가 안 나온다?
- `coupang_products.json`의 링크 형식 확인
- `food_content.json`의 `coupang_keywords`가 카테고리와 매칭되는지 확인

### YouTube 업로드 권한 오류?
- `YT_REFRESH_TOKEN`이 올바르게 설정되었는지 확인
- 음식 채널을 관리하는 Google 계정으로 다시 인증

### 스케줄 시간 조정하기
`food_shorts_publish.yml`의 `cron`을 수정:
```yaml
cron: '0 9 * * *'        # 매일 09:00 (1편)
cron: '0 9,18 * * *'     # 매일 09:00, 18:00 (2편)
cron: '0 9,15,21 * * *'  # 매일 09:00, 15:00, 21:00 (3편)
```

---

## 📊 수익 구조

| 수입원 | 월 예상 수익 (구독자 10만 기준) |
|---|---|
| YouTube 애드센스 | $500-1,000 |
| 쿠팡 파트너스 | $200-500 |
| **합계** | **$700-1,500** |

*(실제 수익은 채널 성장, CTR, 시청자층에 따라 다릅니다)*

---

## 📝 다음 단계

1. ✅ YouTube 채널 준비
2. ✅ Google Cloud & YouTube API 설정
3. ✅ GitHub Secrets 등록
4. ✅ 쿠팡 파트너스 가입
5. ✅ 콘텐츠 커스터마이즈
6. ✅ 수동 테스트
7. ✅ GitHub Actions 자동화

**모두 완료했다면, 채널이 매일 자동으로 영상을 생성하고 업로드합니다!** 🎉
