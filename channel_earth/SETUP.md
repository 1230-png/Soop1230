# 사람이 해야 하는 것

**새 채널을 만들지 않는다.** @Rush22 (숏츠 79편을 내던 채널)의 방향만 바꿔
「지구의 오늘」로 쓴다. 채널 이름을 바꿔도 **채널 ID 는 그대로**이므로:

| 원래 필요했던 것 | 지금 |
|---|---|
| 유튜브 채널 만들기 | **안 해도 된다** |
| 구글 클라우드 프로젝트 만들기 | **안 해도 된다** — Rush22 것이 그대로 맞는다 |
| YouTube Data API 사용 설정 | **이미 되어 있다** |
| OAuth 동의 화면 프로덕션 게시 | **이미 했다** (2026-09 에) |

남은 것은 아래 여섯 가지다.

---

## 1. 실제 API 응답 확인 (5분, **설치할 것이 없다**)

지금 나머지 전부를 막고 있는 한 가지다. 이 코드를 만든 환경에서 USGS 에
닿지 못해(egress 403) **응답을 한 번도 못 봤다.** 파서는 문서로 공개된
스키마를 보고 쓴 것이라, 실제 형식이 다르면 지금 코드는 전부 헛것이다.

파이썬만 있으면 된다. `pip install` 도 `ffmpeg` 도 필요 없다.

```bash
git clone -b claude/youtube-automation-revenue-govgd7 \
  https://github.com/1230-png/Soop1230.git
cd Soop1230
python3 channel_earth/tools/probe.py
```

**잘 되면** 마지막 줄이 `형식이 우리가 아는 것과 맞다.` 다.

**안 되면** 파일 경로를 알려 준다(`channel_earth/build/usgs_response.json`).
**그 파일과 화면에 찍힌 것을 그대로 보내 달라.** 파서를 고친다.

### 1-b. 영상까지 만들어 보려면 (선택)

```bash
pip install -r channel_earth/requirements.txt
python3 channel_earth/build.py --window day
```

이쪽은 `ffmpeg` 이 있어야 한다 (`winget install ffmpeg` / `brew install ffmpeg`).

---

## 2. `RUSH_*` 시크릿이 **이 저장소에** 있는지 확인

저장소 → Settings → Secrets and variables → Actions. **이름만 보면 된다**
(값은 원래 다시 못 읽는다).

`RUSH_CLIENT_ID` · `RUSH_CLIENT_SECRET` · `RUSH_REFRESH_TOKEN` ·
`RUSH_CHANNEL_ID` 네 개가 있는가?

- **있다** → 2번은 끝. 3번으로.
- **없다** → 아래를 한 번 한다.

> **주의.** 숏츠를 실제로 내던 자동화는 이 저장소가 아니라 **별도 저장소
> `1230-png/rush22`** 에서 돌았고, 그쪽 시크릿 이름은 `YOUTUBE_*` 다.
> **시크릿은 저장소를 넘나들지 않는다.** 그쪽에 있다고 여기서 쓰이지 않는다.

### 없을 때만: 값 세 개 다시 만들기 (10분)

구글 클라우드 프로젝트도 채널도 그대로라 **새로 만드는 것은 없다.**
값만 다시 꺼내면 된다.

1. 구글 클라우드 → 그 프로젝트 → 사용자 인증 정보 → 쓰던 OAuth 클라이언트 →
   JSON 내려받기 (`client_id` 와 `client_secret` 은 언제든 다시 볼 수 있다)
2. 리프레시 토큰만 다시 발급한다. 본인 컴퓨터에서:
   ```bash
   python3 channel_earth/get_refresh_token.py \
     --client-secret ~/Downloads/client_secret_*.json
   ```
   **기존 토큰이 무효가 되지 않는다** — 같은 클라이언트에 여러 개가 공존한다
3. 찍힌 세 값을 `RUSH_CLIENT_ID` · `RUSH_CLIENT_SECRET` ·
   `RUSH_REFRESH_TOKEN` 으로 등록
4. `RUSH_CHANNEL_ID` 는 짐작해서 넣지 않는다. 앞의 셋만 넣고 워크플로를
   `upload=true` 로 한 번 돌리면 **자격 증명이 실제로 가진 채널 ID 를 찍고
   멈춘다.** 그 값을 그대로 넣는다

> 내려받은 `client_secret_*.json` 은 등록한 뒤 지울 것.

---

## 3. 채널 간판 갈아 끼우기

예전 「머니러시」 문구가 설명란에 그대로 남아 있다. `channel.yaml` 에 적어
둔 값으로 맞춘다.

```bash
export RUSH_CLIENT_ID=... RUSH_CLIENT_SECRET=... RUSH_REFRESH_TOKEN=... RUSH_CHANNEL_ID=...
python3 channel_earth/channel_settings.py --dry-run   # 무엇이 바뀌는지만
python3 channel_earth/channel_settings.py --force     # 실제로
```

`--force` 가 필요한 이유: 기본 동작은 **빈 칸만** 채운다. 실수로 돌렸을 때
남의 글을 지우지 않기 위해서다. 여기서는 일부러 갈아 끼우는 것이라 `--force`
가 정상 경로다.

**손으로 해야 하는 것 둘:**

- **핸들(@)** — API 로 안 바뀐다. YouTube Studio → 맞춤설정 → 기본 정보에서
  `@지구의오늘` 으로. 이미 쓰는 사람이 있으면 못 쓴다
- **프로필 사진·배너** — Studio 에서 직접

> **확인 불가:** 채널 이름(title)이 API 로 실제로 바뀌는지는 여기서 시험해
> 보지 못했다. `--dry-run` 결과에 이름이 들어 있는데도 Studio 에서 안 바뀌어
> 있으면, Studio 에서 직접 바꾸면 된다.

---

## 4. 예전 숏츠 정리

79편이 그대로 남아 있으면 채널 카탈로그가 「대량 생산된 템플릿 영상 79편 +
새 영상 몇 편」으로 보인다. 파트너 프로그램 심사는 채널 전체를 본다.

```bash
python3 channel_earth/tools/purge_videos.py                    # 목록만 (기본)
python3 channel_earth/tools/purge_videos.py --before 2026-09-22 --delete --yes 79
```

**지운 영상은 되돌릴 수 없다.** 그래서 목록을 먼저 찍고, `--yes` 에 개수를
직접 적어야 지운다. `--before` 는 새로 올린 것을 같이 지우는 사고를 막는다.

잃는 것: 그 영상들의 조회수와 댓글. **구독자 수는 그대로다.** 숏폼 시청
시간은 어차피 파트너 프로그램의 3,000시간에 집계되지 않으므로, 수익화
기준으로 잃는 것은 사실상 없다.

할당량 때문에 한 번에 150편까지만 지운다. 79편이면 한 번에 끝난다.

---

## 5. 기본 브랜치에 합치기

**cron 과 workflow_dispatch 는 기본 브랜치의 워크플로만 본다.** 작업
브랜치에만 있으면 Actions 목록에 뜨지도 않는다.

합치면 같이 들어가는 것: `channel_earth/`, `earth_daily.yml`.
같이 **빠지는** 것: `channel_cs/`, `channel_rush22/` 와 그 cron 워크플로 둘.

---

## 6. cron 켜기 — 맨 마지막

1~5 가 끝나고 **영상을 눈으로 한 번 보고 나서** 켠다.

`.github/workflows/earth_daily.yml` 의 `schedule:` 주석을 푼다. 기본값은
23:00 UTC(08:00 KST)에 전날 하루치다. 스케줄러가 25~70분 늦게 뜨는 것은
정상이다.

공개 설정은 `private` 이 기본이다 — 사람이 보고 직접 공개하라는 뜻이다.

---

## 별도 저장소 `1230-png/rush22` 는 어떻게

숏츠를 내던 코드가 거기 있고, cron 은 2026-09-21 에 멈춰 뒀다. **그대로 둬도
된다** — 돌지 않는다. 정리하고 싶으면 GitHub 에서 archive 하면 되고,
거기 있는 `YOUTUBE_*` 시크릿은 지우지 않는 편이 낫다(같은 채널 것이다).

---

## 정리

| 할 일 | 시간 | 막고 있는 것 |
|---|---|---|
| 1. 응답 확인 | 5분 | **지금 이게 전부를 막고 있다** |
| 2. 시크릿 확인 | 2분 (없으면 +10분) | — |
| 3. 채널 간판 | 5분 | 2번 |
| 4. 숏츠 정리 | 5분 | 2번 |
| 5. 브랜치 합치기 | 2분 | 1번 |
| 6. cron 켜기 | 1분 | 전부 |
