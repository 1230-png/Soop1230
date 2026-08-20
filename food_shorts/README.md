# 🍜 Food Shorts - 자동 영상 생성 시스템

## 🎯 한눈에 보기

**상태**: ✅ 완전 자동화 구성 (영상 생성) + 수동 업로드

| 항목 | 상태 | 경로 |
|------|------|------|
| 영상 자동 생성 | ✅ 완료 | `/home/user/Soop1230/food_shorts/scripts/generate_video.py` |
| 생성된 영상 저장 | ✅ 준비 | `/home/user/Soop1230/food_shorts/output/generated/` |
| 자동 실행 설정 | 📋 필요 | Cron job 설정 필요 (가이드 참고) |
| YouTube 업로드 | 🚀 수동 | 생성된 파일을 YouTube Studio에서 수동 업로드 |

---

## 📁 폴더 구조

```
/home/user/Soop1230/
├── SETUP_GUIDE.md                          ← 📖 설정 가이드 (꼭 읽기!)
├── food_shorts/
│   ├── scripts/
│   │   ├── generate_video.py               ← 영상 생성 스크립트
│   │   └── requirements.txt                ← 필요한 패키지
│   ├── data/
│   │   ├── food_list.json                  ← 영상 소재 데이터
│   │   └── used_videos.csv                 ← 생성 기록
│   └── output/
│       ├── generated/                      ← 🎬 생성된 영상 저장 위치
│       │   ├── food_20260820_140632.mp4
│       │   ├── food_20260820_140632_metadata.json
│       │   ├── food_20260820_140632_bg.png
│       │   └── food_20260820_140632_audio.mp3
│       └── logs/                           ← 자동 실행 로그
│           └── cron.log
└── shared/
    └── common.py                            ← 공유 유틸리티
```

---

## 🚀 빠른 시작 (3단계)

### 1️⃣ PC에서 Cron 설정 (1회만 필요)

```bash
crontab -e
```

맨 아래에 추가:
```
0 9,15,18,21 * * * cd /home/user/Soop1230/food_shorts/scripts && python3 generate_video.py >> /home/user/Soop1230/food_shorts/output/logs/cron.log 2>&1
```

저장: `:wq` (Vim) 또는 Ctrl+X→Y (Nano)

### 2️⃣ 테스트 실행

```bash
python3 /home/user/Soop1230/food_shorts/scripts/generate_video.py
```

### 3️⃣ 생성된 영상 확인

경로: `/home/user/Soop1230/food_shorts/output/generated/`

최신 파일의 `.mp4`를 YouTube에 업로드하고, `.json` 파일의 정보를 사용하면 끝!

---

## 📤 YouTube 업로드 방법

자세한 가이드는 **SETUP_GUIDE.md**의 "Step 4: YouTube에 수동 업로드" 섹션 참고

간단 요약:
1. 생성 폴더 열기: `/home/user/Soop1230/food_shorts/output/generated/`
2. 최신 `.mp4` 파일 + `.json` 메타데이터 선택
3. YouTube Studio → 동영상 업로드
4. 메타데이터 복사-붙여넣기 (제목, 설명, 태그)
5. 공개 → 완료!

---

## 🔧 설정 조정

### 자동 실행 시간 변경

```bash
crontab -e
```

시간 수정 (24시간 형식):
- 현재: `0 9,15,18,21` (09:00, 15:00, 18:00, 21:00)
- 예시: `0 8,12,16,20` (08:00, 12:00, 16:00, 20:00)

### 영상 소재 추가

`food_shorts/data/food_list.json` 수정:
```json
{
  "id": 3,
  "title": "새로운 음식 제목",
  "description": "설명\n\n🛒 Coupang 링크\n\n구독 감사!",
  "tags": ["#태그1", "#태그2"]
}
```

---

## 📊 자동 실행 확인

### 로그 보기 (실시간)

```bash
tail -f /home/user/Soop1230/food_shorts/output/logs/cron.log
```

### 최근 생성 파일 확인

```bash
ls -lh /home/user/Soop1230/food_shorts/output/generated/ | head -5
```

---

## ✅ 체크리스트

- [ ] SETUP_GUIDE.md 읽었음
- [ ] Python3 & ffmpeg 설치 확인
- [ ] Cron job 설정 완료 (`crontab -l`로 확인)
- [ ] 테스트 실행 성공
- [ ] 생성된 영상 확인
- [ ] YouTube 업로드 테스트 완료

---

## 📞 문제 해결

### 영상이 생성 안 됨
→ 로그 확인: `cat /home/user/Soop1230/food_shorts/output/logs/cron.log`

### Python/ffmpeg 없음
→ 설치: SETUP_GUIDE.md의 "⚠️ 주의사항" 섹션 참고

### 한글 깨짐
→ 폰트 설치: SETUP_GUIDE.md의 "⚠️ 주의사항" 섹션 참고

---

## 📝 파일 설명

| 파일 | 용도 |
|------|------|
| `generate_video.py` | 영상 생성 메인 스크립트 |
| `food_list.json` | 영상 소재 (음식 데이터) |
| `used_videos.csv` | 생성 기록 추적 |
| `cron.log` | 자동 실행 로그 |
| `.mp4` | YouTube에 업로드할 영상 |
| `.json` | 메타데이터 (제목/설명/태그) |
| `.png` | 배경 이미지 (삭제 가능) |
| `.mp3` | 오디오 파일 (삭제 가능) |

---

## 🎉 모든 설정 완료!

더 이상 할 일이 없습니다. Cron이 자동으로 작동하니까 안심하고 있으세요!
