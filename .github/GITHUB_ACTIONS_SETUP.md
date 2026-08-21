# 🚀 GitHub Actions 클라우드 자동화 설정 가이드

## 📋 개요

이제 **YouTube 영상이 컴퓨터 없이도 GitHub 클라우드에서 자동으로 생성**됩니다!

- ✅ 24시간 계속 실행 (PC 끌 필요 없음)
- ✅ 일일 4회 자동 생성 (09:00, 15:00, 18:00, 21:00 KST)
- ✅ 생성된 파일은 GitHub Actions 아티팩트로 저장
- ✅ 수동으로 YouTube에 업로드

---

## 🔧 설정 단계

### Step 1: GitHub Actions 워크플로우 확인

이미 `.github/workflows/food-shorts-asmr.yml`이 생성되어 있습니다.

**위치:**
```
1230-png/Soop1230 저장소
└── .github/workflows/food-shorts-asmr.yml
```

---

### Step 2: GitHub에서 Actions 활성화

1. GitHub에서 저장소 열기: https://github.com/1230-png/Soop1230
2. **Settings** (설정) 탭 클릭
3. **Actions** → **General** 클릭
4. **Actions permissions** 에서:
   - `✅ Allow all actions and reusable workflows` 선택
5. **Save** 클릭

---

### Step 3: 워크플로우 수동 실행 테스트

1. **GitHub → Actions** 탭 열기
2. 왼쪽 메뉴에서 **🎬 Food Shorts ASMR 자동 생성** 클릭
3. **Run workflow** 버튼 클릭
4. **Run workflow** 확인 클릭
5. 약 2-3분 후 **녹색 체크 마크** ✅ 확인

---

### Step 4: 자동 스케줄 확인

워크플로우는 다음 시간에 자동으로 실행됩니다:

| 로컬 시간 (한국) | UTC | 설명 |
|---------------|-----|------|
| **09:00** | 00:00 | 아침 생성 |
| **15:00** | 06:00 | 오후 생성 |
| **18:00** | 09:00 | 저녁 생성 |
| **21:00** | 12:00 | 밤 생성 |

---

## 📥 생성된 파일 다운로드

### 방법 1: GitHub UI에서 다운로드 (쉬움)

1. **Actions** 탭 열기
2. **🎬 Food Shorts ASMR 자동 생성** 클릭
3. 최신 실행 기록 선택
4. **Artifacts** 섹션에서 **food-shorts-output** 다운로드
5. ZIP 파일 압축 해제

**다운로드 위치:**
```
food_shorts/output/generated/
├── food_shorts_1.mp4           ← YouTube 업로드 파일
├── metadata_1.json              ← 메타데이터
└── ...
```

### 방법 2: 자동 다운로드 (고급)

GitHub API를 사용해 자동으로 다운로드할 수 있습니다:

```bash
# 최신 아티팩트 다운로드
gh run download <run-id> -n food-shorts-output

# 또는 웹에서 직접 다운로드
curl -H "Authorization: token YOUR_GITHUB_TOKEN" \
  https://api.github.com/repos/1230-png/Soop1230/actions/artifacts \
  | grep "download_url"
```

---

## 🎤 ASMR 효과음 설정

### 음소리 파일 추가

GitHub에 효과음을 업로드하려면:

1. **GitHub 저장소 열기**
2. **Add file** → **Upload files** 클릭
3. 폴더 경로:
   ```
   food_shorts/assets/sounds/
   ```
4. mp3 파일 업로드 (또는 드래그 & 드롭)
5. **Commit changes** 클릭

**또는 Git 명령어 사용:**

```bash
# 로컬에서 효과음 추가
cp my_sound.mp3 food_shorts/assets/sounds/

# 커밋 & 푸시
git add food_shorts/assets/sounds/
git commit -m "Add ASMR sound effects"
git push origin claude/dual-youtube-automation-plan-2f7nmw
```

---

## 📊 실행 상태 모니터링

### GitHub Actions 대시보드

**실시간 모니터링:**
1. 저장소 → **Actions** 탭
2. **🎬 Food Shorts ASMR 자동 생성** 클릭
3. 최신 실행 기록 클릭
4. 각 단계의 상태 확인

**상태 표시:**
- 🟢 **Success** - 성공
- 🟡 **In Progress** - 실행 중
- 🔴 **Failure** - 실패

### 로그 확인

```
저장소 → Actions → 실행 기록 → 클릭 → Logs 탭
```

**주요 로그 위치:**
```
🎬 영상 생성 (Generate Video)
  └─ ffmpeg 실행 로그
  └─ Python 스크립트 출력
  └─ 에러 메시지
```

---

## 🔑 GitHub Secrets (선택사항)

나중에 YouTube 자동 업로드를 추가할 때 필요합니다:

### Secrets 추가 방법

1. **Settings** → **Secrets and variables** → **Actions** 클릭
2. **New repository secret** 클릭
3. 다음 정보 추가:

| 이름 | 값 | 설명 |
|------|-----|------|
| `YOUTUBE_CHANNEL_ID` | (나중에) | YouTube 채널 ID |
| `YOUTUBE_REFRESH_TOKEN` | (나중에) | YouTube OAuth 토큰 |

예시:
```
Name: YOUTUBE_REFRESH_TOKEN
Value: 1//0gH... (실제 토큰 입력)
```

---

## ⚙️ 워크플로우 커스터마이징

### 실행 시간 변경

`.github/workflows/food-shorts-asmr.yml` 편집:

```yaml
schedule:
  - cron: '0 0 * * *'  # 09:00 KST (기본값)
  - cron: '0 6 * * *'  # 15:00 KST
  # ... 시간 수정
```

**Cron 시간 계산기:**
- KST (한국) → UTC 변환: **KST 시간 - 9시간**
- 예: 09:00 KST = 00:00 UTC (0시)
- 예: 15:00 KST = 06:00 UTC (6시)

### 병렬 실행 (고급)

여러 영상을 동시에 생성하려면:

```yaml
jobs:
  generate-video:
    strategy:
      matrix:
        content_id: [1, 2, 3]
    steps:
      - run: |
          python3 generate_video.py --id ${{ matrix.content_id }}
```

---

## 🐛 문제 해결

### ❌ 워크플로우가 실행 안 됨

**원인:** Actions가 비활성화되어 있음

**해결:**
```
Settings → Actions → Allow all actions and reusable workflows
```

### ❌ Python 패키지 설치 실패

**원인:** 네트워크 오류 또는 패키지 버전 불일치

**로그 확인:**
```
Actions → 실행 기록 → Step "Install dependencies" 로그
```

**해결:**
```bash
# 로컬에서 먼저 테스트
pip install -r food_shorts/scripts/requirements.txt

# 성공하면 GitHub에 푸시
git add requirements.txt
git commit -m "Update dependencies"
git push
```

### ❌ FFmpeg 설치 실패

**원인:** 우분투 패키지 레포 문제

**로그 확인:**
```
Actions → 실행 기록 → Step "Install ffmpeg" 로그
```

**해결:** 자동으로 재시도 (대부분 성공)

### ❌ 효과음 파일 찾을 수 없음

**원인:** `assets/sounds/` 폴더가 비어있음

**해결:**
1. 효과음 mp3 파일 추가
2. Git에 커밋 & 푸시
3. 워크플로우 다시 실행

```bash
git add food_shorts/assets/sounds/
git commit -m "Add ASMR sound effects"
git push origin claude/dual-youtube-automation-plan-2f7nmw
```

---

## 📈 사용량 제한 (GitHub 무료 플랜)

**매월 무료 제공:**
- Actions 실행: **2,000분** (월간)
- 저장소당: **500MB** (저장공간)

**계산:**
- 하루 4회 × 3분 = **12분/일**
- 월 30일 = **360분/월** ✅ (충분함)

**초과 시:**
- Pro 플랜: **$21/월** (50,000분)
- 또는 GitHub Copilot Pro: **$20/월** (무제한)

---

## 🎬 다음 단계

1. ✅ Actions 워크플로우 확인
2. ✅ 수동으로 한 번 실행해보기
3. ✅ 생성된 파일 다운로드 & 확인
4. ✅ YouTube에 수동 업로드
5. ✅ (선택) 효과음 추가하기

---

## 💡 팁

**자동 업로드 추가하기 (미래):**
```bash
# YouTube API 설정 후
# 다음 스크립트 추가 가능
python3 upload_to_youtube.py \
  --video_path $VIDEO_PATH \
  --metadata $METADATA_JSON
```

---

## 📞 지원

**문제가 있으면:**
1. GitHub Actions 로그 확인
2. `.github/workflows/food-shorts-asmr.yml` 검토
3. `ASMR_SETUP.md` 설정 확인

더 자세한 정보는 **README.md** 참고
