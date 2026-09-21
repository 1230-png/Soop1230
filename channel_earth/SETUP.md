# 사람이 해야 하는 것

순서대로다. **1번은 지금 바로, 나머지는 1번 결과를 보고** 한다.

---

## 1. 실제 API 응답 확인 (5분, **설치할 것이 아무것도 없다**)

지금 가장 중요한 한 가지다. 이 코드를 만든 환경에서 USGS 에 닿지 못해
(egress 403) **응답을 한 번도 못 봤다.** 파서는 문서로 공개된 스키마를 보고
쓴 것이라, 실제 형식이 다르면 지금 있는 코드는 전부 헛것이다.

파이썬만 있으면 된다. `pip install` 도 `ffmpeg` 도 필요 없다.

```bash
git clone -b claude/youtube-automation-revenue-govgd7 \
  https://github.com/1230-png/Soop1230.git
cd Soop1230
python3 channel_earth/tools/probe.py
```

**잘 되면** 이렇게 끝난다.

```
읽은 건수: 312 / 313
규모 범위: 0.4 ~ 5.9
M4.0 이상: 34건  M5.0 이상: 2건
...
형식이 우리가 아는 것과 맞다. 다음 단계로 가도 된다.
```

**안 되면** 마지막 줄이 파일 경로를 알려 준다
(`channel_earth/build/usgs_response.json`). **그 파일을 그대로 보내 달라.**
화면에 찍힌 것도 같이. 다음 둘 중 하나다.

- `features 배열이 없다` / `한 건도 읽지 못했다` → 스키마가 다르다. 고친다
- `N건은 필요한 값이 없어 제외` 가 대부분 → 칸 이름이 일부 바뀌었다

### 1-b. 영상까지 만들어 보려면 (선택)

형식이 맞는 것을 확인한 뒤, 실제 데이터로 영상을 뽑아 보고 싶으면:

```bash
pip install -r channel_earth/requirements.txt
python3 channel_earth/build.py --window day
```

이쪽은 `ffmpeg` 이 있어야 한다 (`winget install ffmpeg` / `brew install ffmpeg`).
기본 브랜치에 합친 뒤라면 Actions 에서 **「지구의 오늘 — 일일 빌드」**를
손으로 돌려도 된다 — 산출물에 응답과 영상이 같이 붙는다.

---

## 2. 유튜브 채널 만들기

「지구의 오늘」 브랜드 채널. 본인 구글 계정으로만 할 수 있다.

- YouTube → 설정 → 채널 추가
- 채널 이름·설명·키워드는 `channel.yaml` 에 적어 둔 것을 그대로 붙여 넣으면 된다

---

## 3. 구글 클라우드 — 이 채널 전용 프로젝트

**기존 프로젝트를 재활용하지 말 것.** 유튜브 일일 할당량이 채널이 아니라
프로젝트 단위라, 돌려쓰면 다른 채널의 몫을 깎는다.

1. 새 프로젝트 만들기 (이름 아무거나, 예: `earth-today`)
2. **YouTube Data API v3** 사용 설정
3. OAuth 동의 화면 → 외부 → 만들기
4. **게시 상태를 「프로덕션」으로.** ← 여기가 제일 자주 사고 나는 곳이다.
   「테스트」로 두면 **7일 뒤 리프레시 토큰이 폐기되고** 무인 발행이 죽는다.
   앱 확인(verification)은 별개이고 안 받아도 된다 — 경고 문구가 떠도 무시
5. 사용자 인증 정보 → OAuth 클라이언트 ID → **데스크톱 앱** → JSON 내려받기

---

## 4. 리프레시 토큰 받기 (본인 컴퓨터에서 한 번)

```bash
python3 get_refresh_token.py --client-secret ~/Downloads/client_secret_*.json
```

브라우저가 열리면 **「지구의 오늘」을 관리하는 계정**으로 로그인한다.
끝나면 화면에 세 값이 찍힌다.

> 내려받은 `client_secret_*.json` 은 시크릿을 등록한 뒤 지울 것.

---

## 5. GitHub 시크릿 네 개

저장소 → Settings → Secrets and variables → Actions → New repository secret

| 이름 | 값 |
|---|---|
| `EARTH_CLIENT_ID` | 4번에서 찍힌 값 |
| `EARTH_CLIENT_SECRET` | 4번에서 찍힌 값 |
| `EARTH_REFRESH_TOKEN` | 4번에서 찍힌 값 |
| `EARTH_CHANNEL_ID` | **아직 모른다 — 아래 참고** |

채널 ID 는 짐작해서 넣지 않는다. 앞의 셋만 넣고 워크플로를 `upload=true` 로
한 번 돌리면, `upload.py` 가 **그 자격 증명이 실제로 가진 채널 ID 를 찍고
멈춘다.** 그 값을 그대로 네 번째 시크릿에 넣으면 된다.

---

## 6. 기본 브랜치에 합치기

**cron 과 workflow_dispatch 는 기본 브랜치의 워크플로만 본다.** 작업
브랜치에만 있으면 Actions 목록에 뜨지도 않는다.

합치기 전에 확인할 것: 이 브랜치에는 예전에 만들다 만 `channel_rush22/`
커밋이 섞여 있었다. 같이 딸려 왔던 워크플로 두 개(`run_rush22.yml`,
`daily_build.yml`)는 **접기로 한 숏츠 채널로 하루 두 번 발행하는 cron** 을
달고 있어서 지웠다. 혹시 되살아나 있으면 합치기 전에 다시 지울 것.

---

## 7. cron 켜기 — 맨 마지막

1~5 번이 끝나고, **영상을 눈으로 한 번 보고 나서** 켠다.

`.github/workflows/earth_daily.yml` 의 `schedule:` 블록 주석을 푼다.
기본값은 23:00 UTC(08:00 KST)에 전날 하루치다. 스케줄러는 25~70분 늦게
뜨는 일이 흔한데 정상이다.

공개 설정은 `private` 이 기본이다. 사람이 보고 직접 공개하라는 뜻이고,
바꾸려면 워크플로 입력에서 `privacy` 를 적어 줘야 한다.

---

## 정리

| 할 일 | 걸리는 시간 | 막고 있는 것 |
|---|---|---|
| 1. 응답 확인 | 5분 | **지금 이게 전부를 막고 있다** |
| 2. 채널 만들기 | 5분 | — |
| 3. GCP 프로젝트 | 15분 | 2번 |
| 4. 토큰 발급 | 5분 | 3번 |
| 5. 시크릿 등록 | 5분 | 4번 |
| 6. 브랜치 합치기 | 2분 | 1번 |
| 7. cron 켜기 | 1분 | 전부 |
