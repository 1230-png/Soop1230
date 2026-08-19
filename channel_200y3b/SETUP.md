# @200-y3b 자동화 채널 — 설정 가이드 (전부 무료)

채널: https://www.youtube.com/@200-y3b
포맷: **하루 한마디 (One Line A Day)** — 30~40초 세로 쇼츠, 위로/동기부여 한 줄 문장 +
잔잔한 배경 이미지 + 무료 TTS 내레이션 + 자막. 오리지널 문구만 사용(저작권 문제 없음).

이 문서의 6단계만 완료하면, 이후 콘텐츠 생성/업로드/스케줄링은 GitHub Actions가
자동으로 처리합니다. 전부 무료 등급 안에서만 동작하도록 설계했습니다.

## 1. Google Cloud 프로젝트 생성

https://console.cloud.google.com → 새 프로젝트 생성 (무료)

## 2. YouTube Data API v3 활성화

좌측 메뉴 "API 및 서비스" → "라이브러리" → "YouTube Data API v3" 검색 → **사용 설정**

## 3. OAuth 동의 화면 설정

"API 및 서비스" → "OAuth 동의 화면"
- User Type: **외부(External)**
- 앱 이름 등 기본 정보만 입력, 게시 상태는 "테스트 중"으로 두어도 됩니다
- "테스트 사용자"에 `@200-y3b` 채널을 관리하는 본인 구글 계정 이메일 추가

## 4. OAuth 클라이언트 ID 생성

"사용자 인증 정보" → "사용자 인증 정보 만들기" → "OAuth 클라이언트 ID"
- 애플리케이션 유형: **데스크톱 앱**
- 생성 후 우측의 다운로드 버튼으로 `client_secret.json` 저장

## 5. Refresh Token 발급 (딱 한 번, 본인 컴퓨터에서 실행)

```bash
pip install google-auth-oauthlib
python3 scripts/get_refresh_token.py --client-secret client_secret.json
```

브라우저가 열리면 `@200-y3b`를 관리하는 계정으로 로그인하고 권한을 허용하세요.
터미널에 아래처럼 출력됩니다:

```
client_id:     xxxxxxxx.apps.googleusercontent.com
client_secret: xxxxxxxx
refresh_token: 1//xxxxxxxxxxxxxxxxxxxxx
```

## 6. GitHub 저장소에 시크릿 등록

`1230-png/Soop1230` 저장소 → Settings → Secrets and variables → Actions →
"New repository secret"으로 아래 3개를 추가:

| Secret 이름 | 값 |
|---|---|
| `YT_CLIENT_ID` | 5단계에서 나온 client_id |
| `YT_CLIENT_SECRET` | 5단계에서 나온 client_secret |
| `YT_REFRESH_TOKEN` | 5단계에서 나온 refresh_token |

---

## 이후 자동으로 일어나는 일

`.github/workflows/auto_publish.yml`이 스케줄에 따라 자동 실행되어:

1. `scripts/generate_video.py` — 아직 안 쓴 문구를 `content_bank.json`에서 하나 골라
   배경 이미지 생성(Pillow) → 내레이션 생성(gTTS, 무료) → ffmpeg로 영상 합성
2. `scripts/upload_video.py` — 저장된 시크릿으로 YouTube Data API를 통해 업로드
   (기본값: **unlisted** — 처음 몇 개는 검수 후 공개로 바꾸는 걸 권장합니다.
   문제없다 싶으면 워크플로우 파일에서 `PRIVACY_STATUS`를 `public`으로 바꿔주세요)
3. `used_log.csv`에 사용한 문구/업로드 결과를 기록하고 자동 커밋

기본 스케줄은 **매일 1편**입니다 (유튜브 정책상 저품질 대량 업로드는 오히려
불리하므로 빈도를 일부러 낮게 잡았습니다).

## 비용 관련 정말 중요한 점

- YouTube Data API 무료 할당량: 하루 10,000 유닛, 업로드 1회당 약 1,600 유닛 →
  하루 1편은 여유롭게 무료 범위 안입니다.
- GitHub Actions: 개인 계정 기준 매달 무료 분(private repo 2,000분)이 있고,
  이 파이프라인은 1회 실행에 몇 분 이내라 무료 범위를 넘지 않습니다.
- gTTS, Pillow, ffmpeg: 전부 무료/오픈소스, API 키나 결제 불필요.
- **어디에도 신용카드 등록이나 유료 API 키가 필요한 구간이 없습니다.**
