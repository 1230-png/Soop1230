# 기묘한 현실 — 설치 및 인증 안내

## 0. 지금 겪는 `invalid_client` 오류부터

이 오류는 **자격증명이 만료돼서가 아니라, 시크릿 이름이 어긋나서** 났을 가능성이 큽니다.

기존 시크릿 이름은 `FOOD_YT_REFRESH_TOKEN`이었는데 코드가 읽던 이름은 `FOOD_REFRESH_TOKEN`이었습니다.
이름이 맞지 않으면 예전 코드의 폴백(`or YT_CLIENT_ID`)이 작동해 **다른 채널(200y3b)의
client_id/secret을 대신 집어왔습니다.** 한 프로젝트의 client_id에 다른 프로젝트의 refresh_token을
붙이면 Google은 정확히 `invalid_client`를 돌려줍니다.

**이번 개편에서 그 폴백을 완전히 제거했습니다.** 이제 시크릿 이름이 틀리면 조용히 남의
자격증명을 쓰는 대신 즉시 멈추고 어떤 이름이 없는지 알려 줍니다.

---

## 1. Google Cloud 프로젝트 만들기

1. https://console.cloud.google.com 접속
2. 상단 프로젝트 선택 → **새 프로젝트** → 이름은 아무거나 (예: `weird-shorts`)
3. 좌측 **API 및 서비스 → 라이브러리** → `YouTube Data API v3` 검색 → **사용 설정**

## 2. OAuth 동의 화면 — ⚠️ 여기가 가장 중요합니다

1. **API 및 서비스 → OAuth 동의 화면**
2. User Type: **외부(External)** 선택 → 만들기
3. 앱 이름, 사용자 지원 이메일, 개발자 연락처 입력 (나머지는 비워도 됩니다)
4. **⚠️ 게시 상태를 "프로덕션"으로 전환하세요.**

> **"테스트 중" 상태로 두면 refresh token이 7일마다 만료됩니다.**
> 매주 인증이 깨지는 원인이 바로 이것입니다. 반드시 **앱 게시** 버튼을 눌러
> 상태를 **프로덕션**으로 바꿔 두세요.
> 본인만 쓰는 앱이라 Google 심사는 필요 없습니다. 경고 화면이 떠도 그대로 진행하면 됩니다.

## 3. OAuth 클라이언트 발급

1. **API 및 서비스 → 사용자 인증 정보 → 사용자 인증 정보 만들기 → OAuth 클라이언트 ID**
2. 애플리케이션 유형: **데스크톱 앱**
3. 만들어진 클라이언트의 **JSON 다운로드** → `client_secret.json` 으로 저장

## 4. refresh token 발급 (로컬 PC에서 1회)

이 단계는 브라우저 로그인이 필요해서 **본인 PC에서만** 됩니다. GitHub Actions에서는 못 합니다.

```bash
cd channel_food/scripts
pip install -r requirements.txt
python3 get_refresh_token.py --client-secret /경로/client_secret.json
```

브라우저가 열리면 **이 채널의 구글 계정**으로 로그인하고 권한을 허용하세요.
터미널에 세 값이 출력됩니다:

```
client_id     = ...apps.googleusercontent.com
client_secret = GOCSPX-...
refresh_token = 1//0e...
```

## 5. GitHub Secrets 등록 — 이름을 정확히 맞출 것

https://github.com/1230-png/Soop1230/settings/secrets/actions

**New repository secret**으로 아래 3개를 등록합니다. 이름이 **한 글자라도 다르면 인증이 실패합니다.**

| Name (정확히 이대로) | Value |
|---|---|
| `WEIRD_CLIENT_ID` | 위 `client_id` |
| `WEIRD_CLIENT_SECRET` | 위 `client_secret` |
| `WEIRD_REFRESH_TOKEN` | 위 `refresh_token` |

**등록 후 기존 시크릿은 삭제하세요:**
`FOOD_CLIENT_ID`, `FOOD_CLIENT_SECRET`, `FOOD_REFRESH_TOKEN`,
`FOOD_YT_REFRESH_TOKEN`, `ELEVENLABS_API_KEY`

> GitHub은 보안상 등록된 시크릿 값을 다시 보여 주지 않습니다. 값을 잊었다면
> 4단계를 다시 실행해 새로 발급받으면 됩니다.

## 6. 첫 실행 — 반드시 private으로 먼저

https://github.com/1230-png/Soop1230/actions/workflows/weird_shorts_publish.yml

→ **Run workflow** → 공개 범위 **private** (기본값) → 실행

성공하면 YouTube Studio에 비공개 영상이 하나 올라와 있습니다. 확인 후 문제가 없으면
다음부터는 매일 06:00(KST)에 자동으로 공개 업로드됩니다.

---

## 7. 채널 이름과 핸들 변경 — 수동으로만 가능합니다

**YouTube Data API v3로는 채널 이름과 핸들을 바꿀 수 없습니다.**
핸들 변경 엔드포인트가 API에 아예 없고, `brandingSettings.channel.title`도
`channels.update`로 기록되지 않습니다. 스크립트로 자동화할 수 없는 부분입니다.

YouTube Studio에서 직접 바꾸세요 (각 1분):

| 항목 | 경로 |
|---|---|
| 채널 이름 | YouTube Studio → 맞춤설정 → 브랜딩 → 이름 |
| 핸들(@) | YouTube Studio → 맞춤설정 → 기본 정보 → 핸들 |

> 핸들은 **14일에 2회**까지만 바꿀 수 있습니다.

바꾼 뒤 `channel_food/scripts/brand.py`의 `CHANNEL_NAME`과 `CHANNEL_HANDLE`을
같은 값으로 맞춰 주세요. 이 두 상수만 고치면 영상 자막·설명문·채널 정보에 일괄 반영됩니다.

**설명문과 키워드는 자동화됩니다:**
https://github.com/1230-png/Soop1230/actions/workflows/channel_branding.yml
→ Run workflow (이미 설정된 값을 덮어쓰려면 force 체크)

---

## 비용

전부 무료입니다. 결제 수단을 등록할 곳이 없습니다.

| 항목 | 사용하는 것 | 한도 |
|---|---|---|
| 음성 | edge-tts (Microsoft 무료 신경망 음성) | 무제한, API 키 불필요 |
| 배경음 | ffmpeg 자체 합성 | 무제한, 음원 저작권 없음 |
| 영상 | Pillow + ffmpeg | 무제한 |
| 실행 | GitHub Actions | 공개 저장소는 무제한 / 비공개는 월 2,000분 |
| 업로드 | YouTube Data API | 일 10,000 units, 업로드 1회당 1,600 |

ElevenLabs는 쓰지 않습니다. 유료 전환 여지를 없애려고 API 키 주입 자체를 제거했습니다.

## 안전장치

- **하루 1편** (`common.py`의 `MAX_DAILY_UPLOADS`) — 생성 단계와 업로드 단계에서 각각 검사합니다.
  수동으로 워크플로를 여러 번 눌러도 두 번째부터는 영상을 만들지 않고 종료합니다.
- **할당량 초과 시 즉시 중단** — 재시도가 할당량을 더 태우므로 재시도하지 않습니다.
- **로그가 손상되면 차단** — 읽을 수 없는 로그를 "0건"으로 넘기면 무제한 업로드로 이어지므로,
  한도에 도달한 것으로 간주하고 막습니다.
- **실행 시간 상한 15분** — 행이 걸린 잡이 무료 실행 시간을 태우지 않게 합니다.

## 문제가 생기면

| 증상 | 원인과 해결 |
|---|---|
| `invalid_client` | client_id/secret이 refresh_token과 다른 프로젝트의 것입니다. 4~5단계를 다시 하세요. |
| `invalid_grant` | refresh token 만료. OAuth 동의 화면이 "테스트 중"이면 7일마다 만료됩니다 → **2단계에서 프로덕션으로 게시**하고 재발급하세요. |
| `필수 시크릿이 없습니다` | 시크릿 이름 오타입니다. 5단계의 표와 정확히 대조하세요. |
| `quotaExceeded` | 오늘 할당량 소진. 다음 날 자동으로 초기화됩니다. |
| 업로드는 됐는데 로그가 안 남음 | `used_log.csv` 헤더에 `youtube_video_id`, `status` 컬럼이 있는지 확인하세요. |
