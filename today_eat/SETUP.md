# 오늘뭐먹지-f2d 채널 자동화 설정

YouTube 쇼츠 자동 업로드 시스템입니다.

## 📋 설정 단계

### 1. Google API 토큰 추출

[모바일 환경용 Google API OAuth 토큰 추출](../MOBILE_API_TOKEN_GUIDE.md) 가이드를 참고하여 다음 정보를 추출하세요:
- `YT_CLIENT_ID`
- `YT_CLIENT_SECRET`
- `YT_REFRESH_TOKEN`

### 2. GitHub Secrets 등록

저장소의 **Settings → Secrets and variables → Actions**에서 다음을 추가하세요:

```
YT_CLIENT_ID=your_client_id
YT_CLIENT_SECRET=your_client_secret
YT_REFRESH_TOKEN=your_refresh_token
```

### 3. 콘텐츠 준비

`content.csv` 파일에 업로드할 콘텐츠를 추가하세요:

```csv
content_id,text,tags
001,오늘은 따뜻한 국밥이 먹고 싶은 날씨네요!,국밥 따뜻함 추천
002,점심에는 바삭한 튀김이 최고!,튀김 바삭함 맛있음
```

## ⏰ 자동화 일정

매일 다음 시간에 자동 업로드:
- **12:00 KST** (UTC 03:00)
- **15:00 KST** (UTC 06:00)
- **18:00 KST** (UTC 09:00)
- **21:00 KST** (UTC 12:00)

## 🔧 디렉토리 구조

```
today_eat/
├── scripts/
│   ├── generate_video.py    # 비디오 생성
│   ├── upload_video.py      # YouTube 업로드
│   └── requirements.txt     # Python 의존성
├── assets/                  # 이미지, 폰트 등
├── output/                  # 생성된 비디오 (임시)
├── content.csv             # 업로드할 콘텐츠
├── used_log.csv            # 사용한 콘텐츠 기록
└── SETUP.md                # 이 파일
```

## 🚀 수동 실행

테스트 또는 긴급 업로드:

```bash
cd today_eat

# 파이썬 환경 설정
pip install -r scripts/requirements.txt

# 비디오 생성
video_id=$(python3 scripts/generate_video.py)

# YouTube 업로드 (환경변수 필요)
python3 scripts/upload_video.py --video-id $video_id --privacy-status public
```

## ⚠️ 주의사항

- **콘텐츠.csv**: 새 콘텐츠를 계속 추가하세요. 없으면 자동화가 중단됩니다.
- **used_log.csv**: 자동으로 관리되며, 사용한 콘텐츠 기록이 저장됩니다.
- **토큰 보안**: GitHub Secrets을 항상 사용하세요. 커밋하지 마세요!
- **비디오 포맷**: 자동으로 1080x1920 (쇼츠) 형식으로 생성됩니다.

## 📊 로그 확인

업로드 기록은 `used_log.csv`에 저장됩니다:

```csv
content_id,text,used_at
001,오늘은 따뜻한 국밥이 먹고 싶은 날씨네요!,2026-08-20T12:00:00
002,점심에는 바삭한 튀김이 최고!,2026-08-20T15:00:00
```

## 🆘 문제 해결

**"콘텐츠 없음" 에러**
- `content.csv` 파일에 사용 가능한 콘텐츠가 있는지 확인하세요.

**"토큰 인증 실패" 에러**
- GitHub Secrets의 토큰 값이 정확한지 확인하세요.
- [Google API 토큰 재추출](../MOBILE_API_TOKEN_GUIDE.md) 가이드를 따르세요.

**"비디오 생성 실패" 에러**
- ffmpeg, Python 의존성이 설치되어 있는지 확인하세요.
- 한글 폰트가 설치되어 있는지 확인하세요.

