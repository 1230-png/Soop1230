# 🍳 음식 쇼츠 자동화 채널

**요리 + 음식 리뷰 + 주방용품 소개** 콘텐츠의 완전 자동화 유튜브 쇼츠 채널

- 📅 **생성**: 매일 2-3편 자동 생성
- 🎬 **형식**: 30초 수직 쇼츠 (1080x1920)
- 🎤 **음성**: edge-tts 뉴럴 음성 (무료, 한국어)
- 🛒 **수익**: YouTube 애드센스 + 쿠팡 파트너스
- ⚙️ **기술**: Python, ffmpeg, YouTube API, GitHub Actions

---

## 📂 디렉토리 구조

```
channel_food/
├── scripts/
│   ├── generate_food_video.py          # 영상 생성
│   ├── upload_food_video.py            # 업로드 + 쿠팡 링크 삽입
│   ├── food_content.json               # 콘텐츠 데이터베이스
│   ├── coupang_products.json           # 쿠팡 상품 매칭
│   ├── common.py                       # 공용 라이브러리
│   ├── get_refresh_token.py            # YouTube API 인증
│   └── requirements.txt
├── output/                             # 생성된 영상 (git 무시)
├── used_log.csv                        # 사용 기록
├── SETUP.md                            # 📖 설정 가이드
└── README.md                           # 이 파일
```

---

## 🚀 빠른 시작

### 1. 설정 (처음 한 번만)
```bash
# SETUP.md의 8단계를 완료하세요
cd channel_food
cat SETUP.md
```

### 2. 로컬 테스트
```bash
cd channel_food/scripts
python3 generate_food_video.py
```

### 3. 자동화 활성화
- `.github/workflows/food_shorts_publish.yml` 확인
- GitHub Actions 탭에서 워크플로우 상태 모니터링

---

## 📝 콘텐츠 추가하기

### 음식 콘텐츠 추가
`scripts/food_content.json`에 새로운 항목:

```json
{
  "id": 9,
  "type": "recipe",
  "title": "3분 계란볶음밥",
  "description": "남은 밥으로 만드는 초간단 계란볶음밥",
  "korean": "계란볶음밥",
  "English": "Egg fried rice",
  "ingredients": ["계란", "밥", "간장"],
  "coupang_keywords": ["계란", "밥", "팬"],
  "duration_sec": 30,
  "hashtags": ["#밥", "#계란", "#간단요리"]
}
```

### 쿠팡 상품 추가
`scripts/coupang_products.json`에 새로운 상품:

```json
{
  "name": "코팍 냉동밥",
  "link": "https://www.coupang.com/vp/products/YOUR_LINK",
  "keywords": ["밥", "냉동밥", "편의식"]
}
```

---

## 🛠️ 수동 실행

### 영상 생성만
```bash
cd channel_food/scripts
python3 generate_food_video.py
```

### 직접 업로드
```bash
python3 upload_food_video.py \
  --video-path output/food_shorts_1.mp4 \
  --metadata-path output/metadata_1.json \
  --privacy-status public
```

---

## 📊 콘텐츠 타입

| 타입 | 설명 | 예시 |
|---|---|---|
| `recipe` | 간단한 요리법 | 계란말이, 라면 업그레이드 |
| `review` | 음식/상품 리뷰 | 편의점 신상 후기, 라면 순위 |
| `product` | 주방용품 소개 | 에어프라이어, 냉동만두 |

---

## 🎯 수익 흐름

```
영상 조회 ────→ YouTube 애드센스
           ├─→ 쿠팡 링크 클릭 ────→ 쿠팡 파트너스 커미션
           └─→ 구독 ────────────→ 채널 성장
```

---

## ⚙️ GitHub Actions 스케줄

기본 설정: **매일 09:00, 15:00, 21:00 (UTC 기준)**

수정하려면 `.github/workflows/food_shorts_publish.yml`의 `cron` 필드를 변경:
```yaml
cron: '0 9,15,21 * * *'  # 3편 (기본값)
cron: '0 9,18 * * *'     # 2편
cron: '0 9 * * *'        # 1편
```

---

## 🐛 트러블슈팅

### 영상 생성 실패
```bash
# 폰트 설치
sudo apt-get install -y fonts-noto-cjk

# ffmpeg 설치
sudo apt-get install -y ffmpeg
```

### YouTube 업로드 오류
- `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` 확인
- SETUP.md의 **Step 3** 다시 실행

### 쿠팡 링크가 설명에 안 나온다
- `coupang_products.json`의 링크 형식 확인
- `food_content.json`의 `coupang_keywords` 확인

---

## 📖 상세 설정

모든 설정 방법은 **[SETUP.md](./SETUP.md)**에 있습니다.

---

## 📞 지원

오류나 문제가 있으면:
1. GitHub Issues 작성
2. `.github/workflows/food_shorts_publish.yml`의 로그 확인
3. `channel_food/output/` 폴더의 생성 결과 확인

---

## 📜 라이선스

MIT License - 자유롭게 수정 & 배포 가능

---

**행운을 빕니다! 맛있는 콘텐츠로 채널을 채워보세요! 🍴✨**
