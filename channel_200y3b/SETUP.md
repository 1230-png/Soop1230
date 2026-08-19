# @200-y3b 자동화 채널 — 설정 가이드 (전부 무료)

채널: https://www.youtube.com/@200-y3b
포맷: **매일 영어 한마디 (Daily English Phrase)** — 30초 세로 쇼츠. 실생활 영어 표현
하나 + 한글 뜻 + 예문을 영어/한국어 내레이션으로. (2026-08-19: "하루 한마디" 감성
문구 포맷에서 데이터 기반 피벗 — evergreen 검색 수요, 저경쟁 니치, 오리지널
내레이션 알고리즘 보너스에 맞춰 전환)

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

1. `scripts/generate_video.py` — 아직 안 쓴 표현을 `phrase_bank.json`에서 하나 골라
   배경 이미지 생성(Pillow) → 내레이션 생성(gTTS, 무료) → ffmpeg로 영상 합성
2. `scripts/upload_video.py` — 저장된 시크릿으로 YouTube Data API를 통해 업로드
   (기본값: **public**, 바로 전체공개로 올라갑니다. 다시 검수 모드로 돌리고 싶으면
   워크플로우 파일에서 `DEFAULT_PRIVACY_STATUS`를 `unlisted`로 바꿔주세요)
3. `used_log.csv`에 사용한 문구/업로드 결과를 기록하고 자동 커밋

스케줄은 **하루 3편** (09:00 / 15:00 / 21:00 KST)입니다 — 성장 속도와
스팸처럼 보이지 않는 선 사이의 균형점으로 잡았습니다.

## 비용 관련 정말 중요한 점

- YouTube Data API 무료 할당량: 하루 10,000 유닛, 업로드 1회당 약 1,600 유닛 →
  하루 3편(4,800 유닛)도 여유롭게 무료 범위 안입니다.
- GitHub Actions: 이 저장소는 **public**이라 Actions 실행 시간이 완전 무제한
  무료입니다 (private였다면 매달 2,000분 무료 한도가 있었을 거예요).
- gTTS, Pillow, ffmpeg: 전부 무료/오픈소스, API 키나 결제 불필요.
- **어디에도 신용카드 등록이나 유료 API 키가 필요한 구간이 없습니다.**

## 채널 설정(키워드/설명) 자동 채우기 — 추가 인증 1번 필요

`scripts/update_channel_settings.py`는 채널의 **비어있는** 키워드/설명/기본언어만
채워 넣고, 이미 설정된 값은 절대 건드리지 않습니다. 다만 이 기능은 업로드 권한
(`youtube.upload`)보다 넓은 **채널 관리 권한**(`youtube` 전체 스코프)이 필요해서,
인증을 한 번 더 받아야 합니다.

1. 로컬에서 다시 실행 (같은 `client_secret.json` 사용):
   ```
   py get_refresh_token.py --client-secret client_secret_7   # Tab으로 자동완성
   ```
2. 새로 나온 `refresh_token` 값으로, GitHub 저장소 Settings → Secrets and
   variables → Actions에서 기존 **`YT_REFRESH_TOKEN`을 업데이트** (연필 아이콘
   클릭 → 새 값 붙여넣기 → Update secret). `YT_CLIENT_ID`/`YT_CLIENT_SECRET`은
   그대로 두시면 됩니다.
3. GitHub 저장소 → Actions 탭 → **"Fill empty channel settings (@200-y3b)"**
   워크플로우 → **Run workflow** 버튼으로 1회 수동 실행.

이 스코프 확장은 업로드 워크플로우에도 그대로 적용되므로(더 넓은 권한이 좁은
권한을 포함), 앞으로 업로드도 계속 문제없이 동작합니다.
