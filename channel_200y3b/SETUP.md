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
| `.github/workflows/run_shorts.yml` | 매일 08:00 / 12:30 / 20:30 KST | 쇼츠 1편 생성 + 업로드 |
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
python scripts/get_refresh_token.py --client-id "<클라이언트 ID>" --client-secret "<보안 비밀번호>"
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

## 알아두면 좋은 제약

**영상 길이** — 전화번호 인증이 완료되어 있어 15분 제한이 없습니다 (인증 전
채널은 15분 초과 업로드가 거부됩니다).

**표현 뱅크 크기** — `phrase_bank.json`에 현재 199개 표현이 있습니다. 총정리
영상(mega_compilation.yml)은 ~55~60분을 채우기 위해 뱅크를 한 번 이상
순환하므로 영상 안에서 일부 표현이 반복될 수 있습니다. 반복을 줄이려면
표현을 더 추가하세요.

**쿠팡 파트너스 링크** — `upload_video.py`의 `COUPANG_LINK`는 현재 비어 있고,
비어 있으면 설명란에 아무것도 붙지 않습니다. 실제 링크는 파트너 ID로 조합할 수
없고 partners.coupang.com에서 상품별로 생성해야 합니다.

**YouTube 쇼핑(상품 태그)** — 영상에 쿠팡 상품 카드를 붙이는 기능은 YouTube
파트너 프로그램 가입 + 구독자 500명 이상이어야 열립니다. 자격을 갖추면
YouTube 스튜디오 → 수익 창출 → 쇼핑 탭에서 연결할 수 있습니다.
