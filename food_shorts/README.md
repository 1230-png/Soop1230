# 🎬 Food Shorts ASMR - 자동 영상 생성 시스템

## 🎯 개요

**요리 ASMR 효과음으로 쇼츠 영상을 자동 생성하고 YouTube에 수동 업로드하는 완전 자동화 시스템**

- 📍 **위치**: `/home/user/Soop1230/food_shorts/`
- 🎤 **음성**: TTS 없음 → ASMR 효과음 (야채 깎는 소리, 기름 튀기는 소리 등)
- 📝 **자막**: 자동 생성 (Text Overlay)
- ☁️ **실행**: GitHub Actions (24시간 클라우드 자동화)
- 📤 **업로드**: YouTube에 수동 업로드

---

## ✨ 새로운 기능

| 기능 | 설명 | 상태 |
|------|------|------|
| 🎤 ASMR 효과음 | 요리 소리를 배경음으로 사용 | ✅ 완료 |
| 📝 자막 (Text Overlay) | 요리 단계별 설명을 텍스트로 표시 | ✅ 완료 |
| ☁️ GitHub Actions | 클라우드에서 24시간 자동 실행 | ✅ 완료 |
| 🔄 4회 일일 생성 | 09:00, 15:00, 18:00, 21:00 자동 생성 | ✅ 완료 |
| 📊 효과음 자동 선택 | food_type에 따라 맞는 효과음 선택 | ✅ 완료 |

---

## 📁 폴더 구조

```
/home/user/Soop1230/
├── food_shorts/
│   ├── scripts/
│   │   ├── generate_video.py          ← 📺 영상 생성 메인 스크립트 (ASMR)
│   │   └── requirements.txt           ← 필요한 패키지
│   ├── data/
│   │   ├── food_list.json             ← 🎬 콘텐츠 데이터 (효과음 타입 포함)
│   │   └── used_videos.csv            ← 📊 생성 기록
│   ├── assets/
│   │   └── sounds/                    ← 🎤 ASMR 효과음 저장 폴더
│   │       ├── 채소_칼질음.mp3
│   │       ├── 기름_튀기는소리.mp3
│   │       ├── 불_끓는소리.mp3
│   │       └── ...
│   ├── output/
│   │   ├── generated/                 ← 🎬 생성된 영상 저장 위치
│   │   │   ├── food_shorts_1.mp4
│   │   │   ├── metadata_1.json
│   │   │   └── ...
│   │   └── logs/
│   │       └── github_actions.log
│   ├── README.md                      ← 📖 이 파일
│   └── ASMR_SETUP.md                  ← 🎤 효과음 설정 가이드
├── .github/
│   ├── workflows/
│   │   └── food-shorts-asmr.yml       ← ⚙️ GitHub Actions 워크플로우
│   └── GITHUB_ACTIONS_SETUP.md        ← 📋 클라우드 자동화 가이드
└── shared/
    └── common.py                       ← 🛠️ 공유 유틸리티 (배경, 텍스트 렌더링)
```

---

## 🚀 빠른 시작

### 1️⃣ 로컬 테스트 (선택사항)

```bash
# 패키지 설치
pip install -r food_shorts/scripts/requirements.txt

# 수동 실행
python3 food_shorts/scripts/generate_video.py

# 생성 확인
ls -lh food_shorts/output/generated/
```

### 2️⃣ 효과음 추가

**폴더:** `/home/user/Soop1230/food_shorts/assets/sounds/`

효과음 mp3 파일들을 다음과 같이 저장하세요:
```
채소_칼질음.mp3
기름_튀기는소리.mp3
불_끓는소리.mp3
국물_끓는소리.mp3
계란_깨지는소리.mp3
고기_익는소리.mp3
```

📖 **자세한 가이드**: `ASMR_SETUP.md` 참고

### 3️⃣ GitHub Actions 활성화

1. GitHub 저장소 Settings 열기
2. Actions → General 클릭
3. `Allow all actions and reusable workflows` 선택
4. Save 클릭

📖 **자세한 가이드**: `.github/GITHUB_ACTIONS_SETUP.md` 참고

### 4️⃣ 자동 생성 시작

**자동 생성 시간:**
- ✅ 09:00 (오전 9시)
- ✅ 15:00 (오후 3시)
- ✅ 18:00 (오후 6시)
- ✅ 21:00 (오후 9시)

**수동 실행:**
```
GitHub → Actions → 🎬 Food Shorts ASMR 자동 생성 → Run workflow
```

### 5️⃣ 생성된 파일 다운로드

```
GitHub → Actions → 최신 실행 → Artifacts → food-shorts-output 다운로드
```

### 6️⃣ YouTube 수동 업로드

1. 다운로드한 폴더 열기
2. `food_shorts_1.mp4` 파일 선택
3. YouTube Studio 열기 → 동영상 업로드
4. `metadata_1.json` 의 제목/설명/태그 복사-붙여넣기
5. 공개 → 완료!

---

## 🎬 콘텐츠 추가 (food_list.json)

```json
{
  "id": 5,
  "title": "새로운 요리 제목",
  "korean": "한글 설명",
  "description": "상세 설명",
  "sound_type": "불,국물",  // ← 효과음 카테고리
  "steps": [
    "첫번째 단계 설명",
    "두번째 단계 설명",
    "세번째 단계 설명"
  ],
  "tags": ["#요리", "#ASMR"],
  "coupang_link": "https://www.coupang.com/..."
}
```

**sound_type 옵션:**
- `채소` - 야채 깎는 소리
- `고기` - 고기 익는 소리
- `계란` - 계란 요리 소리
- `기름` - 기름 튀기는 소리
- `불` - 물/음식이 끓는 소리
- `국물` - 국물 소리
- `all` - 모든 효과음

---

## 📊 자동 생성 모니터링

### GitHub Actions 확인

```
https://github.com/1230-png/Soop1230/actions
```

### 로컬 로그 확인

```bash
# 생성 기록 보기
tail -f food_shorts/data/used_videos.csv

# GitHub Actions 로그 보기
tail -f food_shorts/output/logs/github_actions.log
```

---

## 🔧 설정 커스터마이징

### 생성 시간 변경

`.github/workflows/food-shorts-asmr.yml` 편집:

```yaml
schedule:
  - cron: '0 0 * * *'  # 09:00 KST 예시
```

**Cron 시간 (KST → UTC):**
- 09:00 KST = `0 0` (UTC)
- 15:00 KST = `0 6` (UTC)
- 18:00 KST = `0 9` (UTC)
- 21:00 KST = `0 12` (UTC)

### 효과음 수 변경

`generate_video.py` 수정:

```python
sound_paths = pick_asmr_sounds(food_type, count=3)  # ← count 변경
```

---

## ⚙️ 패키지 요구사항

```
Pillow==10.4.0      # 이미지 생성 & 텍스트 렌더링
requests==2.34.2    # HTTP 요청
```

**시스템 요구사항:**
- Python 3.11+
- FFmpeg (자동 설치 via GitHub Actions)
- 한글 폰트 (자동 설치 via GitHub Actions)

---

## 📤 YouTube 업로드 (현재)

### 수동 업로드 방법

1. **아티팩트 다운로드**
   ```
   GitHub Actions → 생성된 영상 다운로드
   ```

2. **YouTube Studio 열기**
   ```
   https://studio.youtube.com
   ```

3. **영상 업로드**
   - 파일: `food_shorts_1.mp4`
   - 제목: `metadata_1.json` → `title` 복사
   - 설명: `metadata_1.json` → `description` 복사
   - 태그: `metadata_1.json` → `tags` 복사

4. **공개**
   ```
   공개 설정 → 게시
   ```

### 자동 업로드 (미래)

YouTube API 설정 후, 다음 파일이 추가될 예정:
```
food_shorts/scripts/upload_to_youtube.py
```

---

## 🎤 효과음 리소스

### 무료 효과음 다운로드

- **YouTube Audio Library**: https://www.youtube.com/audiolibrary
- **Freesound**: https://freesound.org (검색: "cooking ASMR")
- **Zapsplat**: https://www.zapsplat.com (검색: "cooking")
- **BBC Sound Effects**: https://sound-effects.bbcrewind.co.uk

### 효과음 추가 단계

1. mp3 형식의 효과음 다운로드
2. `food_shorts/assets/sounds/` 에 저장
3. Git에 커밋 & 푸시
4. 워크플로우 자동 실행

📖 **자세한 가이드**: `ASMR_SETUP.md` 참고

---

## ✅ 체크리스트

- [ ] 저장소 클론/다운로드
- [ ] GitHub Actions 활성화
- [ ] 효과음 폴더에 mp3 파일 추가
- [ ] food_list.json에서 sound_type 설정
- [ ] 수동으로 한 번 실행 (테스트)
- [ ] 생성된 영상 확인
- [ ] YouTube에 수동 업로드
- [ ] 자동 생성 대기

---

## 🐛 문제 해결

### ❌ 효과음이 들리지 않음

**해결:**
1. `assets/sounds/` 폴더에 mp3 파일이 있는지 확인
2. 파일명이 올바른지 확인 (예: `채소_칼질음.mp3`)
3. 파일을 Git에 커밋했는지 확인

### ❌ 영상이 생성 안 됨

**해결:**
1. GitHub Actions 로그 확인
   ```
   Actions → 실행 기록 → 에러 메시지 확인
   ```
2. 로컬에서 테스트
   ```bash
   python3 food_shorts/scripts/generate_video.py
   ```

### ❌ Python 패키지 설치 실패

**해결:**
```bash
# 로컬에서 설치 테스트
pip install -r food_shorts/scripts/requirements.txt

# 성공 후 GitHub에 푸시
git add .
git commit -m "Update dependencies"
git push
```

---

## 📞 추가 지원

**상세 가이드:**
- 🎤 ASMR 효과음: `ASMR_SETUP.md`
- ☁️ GitHub Actions: `.github/GITHUB_ACTIONS_SETUP.md`

**GitHub Issues:**
```
https://github.com/1230-png/Soop1230/issues
```

---

## 📈 다음 단계

1. ✅ 효과음 추가 (ASMR_SETUP.md 참고)
2. ✅ GitHub Actions 자동 생성 대기
3. ✅ YouTube에 수동 업로드
4. 🚀 (선택) YouTube API 자동 업로드 구현

---

## 🎉 완료!

더 이상 할 일이 없습니다.
**GitHub Actions가 자동으로 영상을 생성하면, YouTube에 수동으로 업로드하면 끝!**

행운을 빕니다! 🚀📺
