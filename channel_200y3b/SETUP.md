# @200-y3b 자동화 채널 — 설정 가이드

채널: https://www.youtube.com/@200-y3b
포맷: **매일 영어 한마디** — 30초 세로 쇼츠. 실생활 영어 표현 하나 + 한글 뜻 +
예문을 영어/한국어 내레이션으로.

**현재 상태: 완전 자동화 동작 중.** 컴퓨터를 켜둘 필요 없이 GitHub Actions가
클라우드에서 실행합니다. 전화번호 인증도 완료되어 15분 제한 없이 업로드할 수
있습니다. 아래는 처음부터 다시 세팅하거나, 키가 만료됐을 때 참고하는 문서입니다.

---

## 자동으로 돌아가는 것

| 워크플로우 | 스케줄 | 하는 일 |
|---|---|---|
| `.github/workflows/run_shorts.yml` | 매일 09:00 / 15:00 / 21:00 KST | 쇼츠 1편 생성 + 업로드 |
| `.github/workflows/longform_publish.yml` | 매주 일요일 20:00 KST | 표현 30개 모음 ~5분 롱폼 1편 생성 + 업로드 |
| `.github/workflows/mega_compilation.yml` | 매월 1일 18:00 KST | 표현 뱅크를 순환하며 ~55~60분 총정리 영상 1편 생성 + 업로드 |

각 실행마다: `phrase_bank.json`에서 표현을 고름 → 배경 이미지 생성(Pillow) →
내레이션 생성(edge-tts) → ffmpeg로 영상 합성 → YouTube 업로드 →
`used_log*.csv`에 기록 후 자동 커밋.

쇼츠·롱폼·총정리는 각각 다른 사용 기록/커서를 관리해서 순환합니다. 총정리는
표현 뱅크가 고정된 풀이라 매주가 아니라 매월 한 번만 돌립니다 — 더 자주 돌리면
같은 내용을 반복할 뿐입니다.

생성된 영상·오디오 파일은 러너의 임시 디렉토리(`SHORTS_OUTPUT_DIR`)에 쓰고
저장소에는 커밋하지 않습니다. 로컬에서 직접 실행하면 이 값이 없으므로
`channel_200y3b/output/`에 저장됩니다.

> **중요:** 스케줄(`cron`)은 저장소의 **기본 브랜치**에 있는 워크플로우 파일만
> 인식합니다. 워크플로우를 수정할 때는 반드시 기본 브랜치에 반영해야 합니다.

---

## 필요한 GitHub Secrets

저장소 → Settings → Secrets and variables → Actions

| Secret 이름 | 발급처 |
|---|---|
| `Y3B_CLIENT_ID` | Google Cloud Console OAuth 클라이언트 (이 채널 전용) |
| `Y3B_CLIENT_SECRET` | 〃 |
| `Y3B_REFRESH_TOKEN` | 아래 "Refresh Token 발급" 참고 |

`YT_CLIENT_ID` / `YT_CLIENT_SECRET` / `YT_REFRESH_TOKEN`은 이 저장소의 다른
채널과 공유되는 폴백 값입니다. `Y3B_*`가 있으면 그걸 우선 사용하고, 없으면만
`YT_*`로 넘어갑니다 — 다른 채널이 자기 시크릿을 회전시켜도 이 채널이 같이
깨지지 않도록 하는 안전장치입니다. `upload_video.py`는 업로드 직전에
`channels().list(mine=True)`로 실제 채널 ID를 확인해서, 자격 증명이 @200-y3b가
아니면 업로드를 거부합니다.

TTS(edge-tts)는 API 키가 필요 없습니다 — 무료·무제한, 별도 시크릿 없음.

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
>
> 클라이언트가 삭제되면(`deleted_client` 오류) 여기서 새로 만들고, 아래 5번부터
> 다시 하면 됩니다.

### 5. Refresh Token 발급 (본인 컴퓨터에서 한 번)

```bash
pip install -r scripts/requirements.txt

# 값을 직접 넣거나
python scripts/get_refresh_token.py \
    --client-id "<클라이언트 ID>" --client-secret "<보안 비밀번호>"

# Console 에서 받은 JSON 을 주거나
python scripts/get_refresh_token.py --client-secret-file client_secret.json
```

브라우저가 열리면 **반드시 `@200-y3b`를 관리하는 계정으로** 로그인하고 권한을
허용하세요. 다른 계정으로 로그인하면 업로드가 그 계정 채널로 시도되다가
`upload_video.py`의 채널 확인 로직에 막혀 실패합니다 (이 문제가 실제로 한 번
있었습니다).

스크립트가 발급받은 토큰을 **그 자리에서 검증**하고, 성공하면
`channel_200y3b/.env.youtube`에 저장합니다(이 파일은 gitignore 처리되어 있어
저장소에 올라가지 않습니다).

터미널에 출력된 세 값을 `Y3B_CLIENT_ID` / `Y3B_CLIENT_SECRET` /
`Y3B_REFRESH_TOKEN`으로 GitHub Secrets에 등록하면 됩니다.

> `invalid_grant` 오류가 나면 대부분 토큰을 손으로 옮겨 적다 생긴 오타입니다.
> 스크립트가 "✅ Refresh token verified working"까지 찍었는지 확인하세요.

### 6. 동작 확인

저장소 → Actions 탭 → **"200-y3b Daily Shorts"** → **Run workflow**로 수동 실행.
로그에 `✅ Uploaded: ...`가 나오면 정상입니다.

---

## 음성 — edge-tts

`common.py`가 영어/한국어 모두 Microsoft edge-tts(`en-US-GuyNeural` /
`ko-KR-InJoonNeural`)로 생성합니다. API 키가 필요 없고 무료·무제한이라
사용량 한도를 신경 쓸 필요가 없습니다.

> 과거에는 ElevenLabs(월 10,000자 무료)를 썼지만, 키가 401을 반환하며 반복
> 실패했습니다(무료 한도 초과 또는 다른 프로젝트와의 키 공유 충돌로 추정).
> API 키 자체가 실패 지점이 되는 걸 없애기 위해 edge-tts로 완전히 교체했습니다.

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
- **edge-tts**: 무료·무제한 (API 키 없음).
- Pillow, ffmpeg: 무료/오픈소스.

신용카드 등록이 필요한 구간은 없습니다.

---

## 채널 뒷정리

무인 발행이라 실패한 흔적을 아무도 보지 않습니다. Actions 탭 →
**"Channel housekeeping (@200-y3b)"** → Run workflow 로 손수 돌립니다.

| action | 하는 일 |
|---|---|
| `audit` | 업로드 설정·중복·재생목록 누락을 한 번에 본다 (읽기만) |
| `backfill-preview` / `backfill-apply` | 재생목록에 못 들어간 영상을 제목 규칙대로 채운다 |
| `playlist-add` | 영상 하나를 지정한 재생목록에 넣는다 |
| `dedupe-preview` | 같은 표현이 두 번 올라간 것을 찾는다 |
| `dedupe-private` | 중복분을 비공개로 돌린다 (되돌릴 수 있다) |
| `dedupe-apply` | 중복분을 삭제한다 (되돌릴 수 없다) |
| `retitle` | 옛 서식으로 올라간 롱폼 제목을 새 검색 서식으로 바꾼다 |
| `comment` | 쇼츠에 롱폼 재생목록으로 가는 채널 댓글을 단다 |
| `stats` | 수익 창출 자격까지 남은 거리 (읽기만) |

상태를 바꾸는 것은 전부 미리보기가 먼저입니다. 중복은 되도록
`dedupe-private` 로 처리하세요 — 공개 채널에서는 똑같이 사라지지만 조회수와
댓글이 남고 다시 공개할 수 있습니다.

먼저 올라간 영상이 항상 원본으로 남습니다.

---

## 손으로 해야 하는 두 가지 (따라 하기)

API 가 없어서 자동화가 안 되는 작업입니다. 한 번만 하면 됩니다.
둘 다 Google Cloud Console 을 거치므로 **한 번에 같이 하는 편이 낫습니다.**

### A. Cloud Console 에서 클라이언트 정보 확인 + 옛 보안 비밀번호 삭제

1. https://console.cloud.google.com/apis/credentials 접속.
   @200-y3b 를 관리하는 **구글 계정으로 로그인**합니다.
2. 화면 맨 위 프로젝트 선택기에서 이 채널을 만들 때 쓴 프로젝트를 고릅니다.
   (프로젝트가 하나뿐이면 이미 선택돼 있습니다.)
3. **"OAuth 2.0 클라이언트 ID"** 목록에서 이름을 눌러 상세 화면으로 들어갑니다.
4. 오른쪽 위 **클라이언트 ID** 를 복사해 둡니다. (B 에서 씁니다.)
5. **"클라이언트 보안 비밀번호"** 목록을 봅니다.
   - **사용 중지됨(비활성)** 으로 표시된 `****FDrF` 오른쪽의 **휴지통 아이콘**을
     눌러 삭제합니다. 사용 중인 것이 아니므로 지워도 발행이 멈추지 않습니다.
   - 남은 **사용 설정됨** 항목의 값이 보이면 복사해 둡니다. 가려져 있으면
     **"+ 보안 비밀번호 추가"** 로 새로 만들고 그 값을 복사합니다.
     이 경우 GitHub Secret 의 `Y3B_CLIENT_SECRET` 도 새 값으로 바꿔야 합니다.
6. 왼쪽 메뉴 **"OAuth 동의 화면"** → 게시 상태가 **"테스트"** 면
   **"앱 게시"** 를 눌러 **프로덕션**으로 바꿉니다.
   테스트 상태에서는 refresh token 이 **7일마다 만료**되어 발행이 멈춥니다.

### B. Y3B_REFRESH_TOKEN 다시 발급

댓글 API(`commentThreads`)는 `youtube.force-ssl` 스코프를 요구하는데 지금
토큰은 `youtube` 만 가지고 있습니다. **스코프는 코드가 아니라 토큰에 붙어
있어서 코드로는 넓힐 수 없고, 구글 로그인 동의가 필요해 자동화도 안 됩니다.**

두 방법 중 하나를 고르세요.

| | B-1 브라우저만 | B-2 스크립트 |
|---|---|---|
| 설치 | 없음 | 파이썬 |
| 바꾸는 Secret | 3개 (클라이언트를 새로 만듦) | 1개 |
| 추천 | 명령줄이 익숙하지 않다면 | 파이썬이 이미 있다면 |

#### B-1. OAuth Playground (설치 없이, 브라우저만)

1. https://console.cloud.google.com/apis/credentials 에서
   **"+ 사용자 인증 정보 만들기"** → **"OAuth 클라이언트 ID"**
2. 애플리케이션 유형: **웹 애플리케이션**. 이름은 아무거나 (예: `playground`).
3. **"승인된 리디렉션 URI"** → **"+ URI 추가"** → 아래를 정확히 붙여넣기:

   ```
   https://developers.google.com/oauthplayground
   ```

4. **만들기** → 뜨는 팝업의 **클라이언트 ID** 와 **클라이언트 보안 비밀번호**
   를 둘 다 복사해 둡니다. (이 팝업을 닫으면 보안 비밀번호를 다시 못 봅니다.)
5. https://developers.google.com/oauthplayground/ 접속 →
   오른쪽 위 **톱니바퀴(⚙)** 클릭
6. **"Use your own OAuth credentials"** 체크 → 4에서 복사한 두 값을 입력.
   같은 패널의 **Access type** 이 **Offline** 인지 확인합니다.
   (Online 이면 refresh token 이 안 나옵니다.)
7. 왼쪽 **Step 1** 맨 아래 **"Input your own scopes"** 칸에 아래를 붙여넣고
   **"Authorize APIs"**:

   ```
   https://www.googleapis.com/auth/youtube.force-ssl
   ```

8. **@200-y3b 를 관리하는 계정**으로 로그인하고 **항목을 끄지 말고** 허용.
9. **Step 2** 의 **"Exchange authorization code for tokens"** 클릭 →
   오른쪽에 나오는 **Refresh token** 값을 복사.
10. GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions** 에서
    **세 개 모두** 새 값으로 바꿉니다:
    `Y3B_CLIENT_ID`, `Y3B_CLIENT_SECRET` (4에서 복사), `Y3B_REFRESH_TOKEN` (9).

> 새 클라이언트를 쓰므로 세 값이 다 바뀝니다. **기존 데스크톱 클라이언트는
> 지우지 마세요** — 새 값이 확인될 때까지 남겨 둡니다.

#### B-2. 스크립트 (파이썬이 있다면)

기존 클라이언트를 그대로 쓰므로 `Y3B_REFRESH_TOKEN` 하나만 바뀝니다.

1. 파이썬이 없으면 https://www.python.org/downloads/ 에서 설치.
   윈도우 설치 화면에서 **"Add python.exe to PATH"** 를 꼭 체크하세요.
2. 터미널(윈도우는 PowerShell)에서:

   ```bash
   pip install google-auth-oauthlib
   ```

3. `channel_200y3b/scripts/get_refresh_token.py` 가 있는 폴더에서:

   ```bash
   python get_refresh_token.py \
       --client-id "A-4 에서 복사한 클라이언트 ID" \
       --client-secret "A-5 에서 복사한 보안 비밀번호"
   ```

4. 브라우저가 열립니다. **반드시 @200-y3b 를 관리하는 계정**으로 로그인하세요.
   다른 계정으로 하면 업로드가 엉뚱한 채널로 가려다 채널 확인 로직에 막힙니다.
5. 동의 화면에서 **항목을 하나도 끄지 말고** 전부 허용합니다.
   하나라도 끄면 스크립트가 경고를 찍고, 나중에 댓글이 조용히 실패합니다.
6. 터미널에 찍힌 `Y3B_REFRESH_TOKEN` 값을 복사해 GitHub 저장소 →
   **Settings** → **Secrets and variables** → **Actions** →
   `Y3B_REFRESH_TOKEN` 의 연필 아이콘 → 붙여넣고 **Update secret**.

#### 어느 쪽이든 끝나면 확인

Actions 탭 → **"Channel housekeeping (@200-y3b)"** → Run workflow →
`comment-preview`. 403 안내 대신 "달 것: ..." 목록이 나오면 성공입니다.
이어서 `comment-apply` 를 돌리면 기존 쇼츠에 댓글이 달립니다.

`audit` 도 한 번 돌려 보세요. 정상이면 업로드 경로도 멀쩡하다는 뜻입니다.

> **토큰은 비밀값입니다.** 채팅·이슈·커밋에 붙여넣지 마세요.
> 붙여넣을 곳은 GitHub Secrets 한 곳뿐입니다.

---

## 알아두면 좋은 제약

**영상 길이** — 전화번호 인증이 완료되어 있어 15분 제한이 없습니다 (인증 전
채널은 15분 초과 업로드가 거부됩니다).

**표현 뱅크 크기** — `phrase_bank.json`에 1000개 표현이 있습니다. 쇼츠가
하루 3편이면 하루 3개를 쓰므로 한 바퀴 도는 데 약 11개월 걸립니다. 롱폼
팩은 별도 커서로 돌아 쇼츠 순서를 건드리지 않습니다.

표현을 더 넣을 때는 영어 원문이 겹치지 않는지 반드시 확인하세요. 겹치면
같은 영상이 두 번 올라갑니다. 대소문자·구두점·아포스트로피를 지우고 비교해야
`I'm` 과 `I am` 같은 차이에 속지 않습니다.

**댓글에는 더 넓은 스코프가 필요합니다** — `commentThreads` API 는
`youtube.force-ssl` 을 요구하고, `youtube` 만으로는
`403 insufficientPermissions` 가 납니다. 코드는 force-ssl 을 요청하도록
고쳐 뒀지만, **이미 발급받은 refresh token 은 스코프가 늘어나지 않습니다.**
쇼츠 댓글을 쓰려면 `get_refresh_token.py` 를 다시 돌려 `Y3B_REFRESH_TOKEN` 을
갈아 끼워야 합니다. 업로드·재생목록·썸네일은 기존 토큰으로도 그대로 돕니다.

**댓글 고정은 자동화할 수 없습니다** — Data API 에 고정(pin) 엔드포인트가
없습니다. 스크립트가 다는 것은 고정되지 않은 채널 댓글이고, 고정은
스튜디오에서 직접 해야 합니다.

**보안 비밀번호를 새로 발급했을 때** — 예전 것은 Google Cloud Console에서
직접 지워야 합니다. OAuth 클라이언트의 보안 비밀번호를 지우는 API 는 없어서
자동화할 수 없는 유일한 항목입니다. "API 및 서비스" → "사용자 인증 정보" →
해당 OAuth 클라이언트 → 사용 중지된 보안 비밀번호의 휴지통 아이콘.
GitHub Secrets 의 `Y3B_CLIENT_SECRET` 이 새 값인지 먼저 확인하고 지우세요.

**쿠팡 파트너스 링크** — `upload_video.py`의 `COUPANG_LINK`는 현재 비어 있고,
비어 있으면 설명란에 아무것도 붙지 않습니다. 실제 링크는 파트너 ID로 조합할 수
없고 partners.coupang.com에서 상품별로 생성해야 합니다.

**YouTube 쇼핑(상품 태그)** — 영상에 쿠팡 상품 카드를 붙이는 기능은 YouTube
파트너 프로그램 가입 + 구독자 500명 이상이어야 열립니다. 자격을 갖추면
YouTube 스튜디오 → 수익 창출 → 쇼핑 탭에서 연결할 수 있습니다.
