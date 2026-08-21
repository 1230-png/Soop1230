# @200-y3b 자동화 채널 — 설정 가이드

채널: https://www.youtube.com/@200-y3b
포맷: **매일 영어 한마디** — 30초 세로 쇼츠. 실생활 영어 표현 하나 + 한글 뜻 +
예문을 영어/한국어 내레이션으로.

**현재 상태: 완전 자동화 동작 중.** 컴퓨터를 켜둘 필요 없이 GitHub Actions가
클라우드에서 실행합니다. 아래는 처음부터 다시 세팅하거나, 키가 만료됐을 때
참고하는 문서입니다.

---

## 자동으로 돌아가는 것

| 워크플로우 | 스케줄 | 하는 일 |
|---|---|---|
| `.github/workflows/run_shorts.yml` | 매일 09:00 / 15:00 / 21:00 KST | 쇼츠 1편 생성 + 업로드 |
| `.github/workflows/longform_publish.yml` | 매주 일요일 20:00 KST | 표현 30개 모음 8~12분 롱폼 1편 생성 + 업로드 |

각 실행마다: `phrase_bank.json`에서 아직 안 쓴 표현을 고름 → 배경 이미지 생성
(Pillow) → 내레이션 생성(ElevenLabs) → ffmpeg로 영상 합성 → YouTube 업로드 →
`used_log.csv`(쇼츠) / `used_log_longform.csv`(롱폼)에 기록 후 자동 커밋.

쇼츠와 롱폼은 서로 다른 사용 기록을 관리해서 표현이 겹치지 않게 순환합니다.

생성된 영상·오디오 파일은 러너의 임시 디렉토리(`SHORTS_OUTPUT_DIR`)에 쓰고
저장소에는 커밋하지 않습니다. 로컬에서 직접 실행하면 이 값이 없으므로
`channel_200y3b/output/`에 저장됩니다.

> **중요:** 스케줄(`cron`)은 저장소의 **기본 브랜치**에 있는 워크플로우 파일만
> 인식합니다. 워크플로우를 수정할 때는 반드시 기본 브랜치에 반영해야 합니다.

---

## 필요한 GitHub Secrets (4개)

저장소 → Settings → Secrets and variables → Actions

| Secret 이름 | 발급처 |
|---|---|
| `ELEVENLABS_API_KEY` | elevenlabs.io → 프로필 → API Keys (`sk_`로 시작) |
| `YT_CLIENT_ID` | Google Cloud Console OAuth 클라이언트 |
| `YT_CLIENT_SECRET` | 〃 |
| `YT_REFRESH_TOKEN` | 아래 "Refresh Token 발급" 참고 |

4개 모두 필수입니다. `ELEVENLABS_API_KEY`가 없으면 내레이션 단계에서 바로
실패합니다(폴백 없음).

---

## 처음부터 세팅하는 경우

### 1~4. Google Cloud OAuth 클라이언트 만들기

1. https://console.cloud.google.com → 새 프로젝트 생성 (무료)
2. "API 및 서비스" → "라이브러리" → **YouTube Data API v3** 사용 설정
3. "OAuth 동의 화면": User Type **외부**, 테스트 사용자에 `@200-y3b` 관리 계정 추가
4. "사용자 인증 정보" → "OAuth 클라이언트 ID" → 애플리케이션 유형 **데스크톱 앱**
   → 생성된 **클라이언트 ID**와 **클라이언트 보안 비밀번호**를 복사

> 보안 비밀번호는 생성 직후 한 번만 전체를 볼 수 있습니다. 놓쳤으면 클라이언트
> 상세 화면에서 **"+ Add secret"**으로 새로 발급하세요.

### 5. Refresh Token 발급 (본인 컴퓨터에서 한 번)

```bash
pip install -r scripts/requirements.txt
python scripts/get_refresh_token.py --client-id "<클라이언트 ID>" --client-secret "<보안 비밀번호>"
```

브라우저가 열리면 `@200-y3b`를 관리하는 계정으로 로그인하고 권한을 허용하세요.
스크립트가 발급받은 토큰을 **그 자리에서 검증**하고, 성공하면
`channel_200y3b/.env.youtube`에 저장합니다(이 파일은 gitignore 처리되어 있어
저장소에 올라가지 않습니다).

터미널에 출력된 세 값을 GitHub Secrets에 등록하면 됩니다.

> `invalid_grant` 오류가 나면 대부분 토큰을 손으로 옮겨 적다 생긴 오타입니다.
> 스크립트가 "✅ Refresh token verified working"까지 찍었는지 확인하세요.

### 6. 동작 확인

저장소 → Actions 탭 → **"200-y3b Daily Shorts"** → **Run workflow**로 수동 실행.
로그에 `✨ Success! Video ID: ...`가 나오면 정상입니다.

---

## 음성 — ElevenLabs

`common.py`가 영어/한국어 모두 ElevenLabs(`eleven_multilingual_v2`)로 생성합니다.
기본 보이스는 "Adam"(`ELEVENLABS_VOICE_ID`로 변경 가능).

무료 한도는 월 10,000자이고, 현재 사용량은 월 약 8,600자로 한도 안에 들어옵니다.
쇼츠 발행 빈도를 늘리면 한도를 넘길 수 있으니 주의하세요.

> 과거에는 gTTS → edge-tts를 거쳤지만, edge-tts는 Bing 음성 서버가 일부 클라우드
> 환경에서 403을 반환해 신뢰할 수 없었습니다. 지금은 ElevenLabs 단독이며
> 폴백이 없으므로, 한도를 소진하면 워크플로우가 실패합니다.

---

## 수동 실행용 도구

| 워크플로우 / 스크립트 | 용도 |
|---|---|
| `.github/workflows/channel_banner.yml` | 채널 배너 이미지 생성 후 적용 |
| `.github/workflows/channel_settings.yml` | 비어있는 채널 키워드/설명만 채움 |
| `scripts/scan_video_links.py` | 업로드된 모든 영상 설명란의 링크 점검 (로컬 실행) |

---

## 비용

- **YouTube Data API**: 하루 10,000 유닛 무료, 업로드 1회당 약 1,600 유닛 →
  하루 3편(약 4,800 유닛)은 여유롭게 무료 범위.
- **GitHub Actions**: 이 저장소는 public이라 실행 시간 무제한 무료.
- **ElevenLabs**: 월 10,000자 무료 (현재 약 8,600자 사용).
- Pillow, ffmpeg: 무료/오픈소스.

신용카드 등록이 필요한 구간은 없습니다.

---

## 알아두면 좋은 제약

**커스텀 썸네일** — 롱폼은 썸네일을 자동 생성해 올리지만, 유튜브는 전화번호
인증이 안 된 채널의 썸네일 업로드를 막습니다. 인증 전에는 썸네일 단계만 조용히
건너뛰고 영상 업로드는 정상 진행됩니다.

**쿠팡 파트너스 링크** — `upload_video.py`의 `COUPANG_LINK`는 현재 비어 있고,
비어 있으면 설명란에 아무것도 붙지 않습니다. 실제 링크는 파트너 ID로 조합할 수
없고 partners.coupang.com에서 상품별로 생성해야 합니다.

**YouTube 쇼핑(상품 태그)** — 영상에 쿠팡 상품 카드를 붙이는 기능은 YouTube
파트너 프로그램 가입 + 구독자 500명 이상이어야 열립니다. 자격을 갖추면
YouTube 스튜디오 → 수익 창출 → 쇼핑 탭에서 연결할 수 있습니다.
