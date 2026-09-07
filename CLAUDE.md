# Soop1230

유튜브 채널 자동화 프로젝트를 모아 둔 모노레포. **각 디렉터리는 서로 독립적이다.**
공유 패키지가 없고 의존성도 따로 관리한다. 한 프로젝트를 고칠 때 다른 프로젝트를
건드리지 않는다.

## 프로젝트 지도

| 디렉터리 | 채널/용도 | 상태 |
|---|---|---|
| `channel_200y3b/` | @200-y3b — 매일 영어 한마디 쇼츠 + 주간 롱폼 + 월간 총정리 | **가동 중** (GitHub Actions 무인 발행) |
| `channel_food/` | 현실 속 기괴한 현상 — 매일 쇼츠 1편 | **가동 중** |
| `channel/` | 새벽공기 — Suno 감성 힙합 플레이리스트 | 문서·기록 위주 (코드 없음) |
| `market-verify/` | 머니로직(MoneyLogic) 롱폼 — 대본·영상·업로드 | 신규, 로컬 실행 |
| `shorts_engine/` | 피드백 루프 쇼츠 파이프라인 (FastAPI + Postgres 큐) | **참고 구현. 지금 돌지 않는다** |

`shorts_engine/`은 규모가 커질 때를 위한 판이다. 매일 발행은 `channel_food/`가 한다.
여기를 "현재 파이프라인"으로 착각하고 고치지 말 것.

디렉터리 이름 `channel_food`는 이전 음식 채널에서 이어받은 것이고 지금 내용은
음식과 무관하다. 워크플로 경로가 묶여 있어 그대로 둔다. 이름 보고 추측하지 말 것.

## 테스트

프로젝트마다 따로 돌린다.

```bash
cd market-verify && python -m pytest      # 네트워크·API 안 탐 (영상 조립까지 돌려 4분)
cd shorts_engine && python -m pytest      # pythonpath=. , asyncio_mode=auto
cd channel_food  && python -m pytest tests/   # ffmpeg·네트워크 불필요
```

새 테스트는 네트워크와 외부 API를 타지 않게 쓴다. 기존 테스트가 전부 그렇게 돼 있다.

## 비밀값

**환경변수로만 다룬다. 코드·커밋·로그에 절대 넣지 않는다.**

- `market-verify` → `ANTHROPIC_API_KEY`
- `channel_200y3b` → `YT_CLIENT_ID` / `YT_CLIENT_SECRET` / `YT_REFRESH_TOKEN`
- `channel_food` → `WEIRD_CLIENT_ID` / `WEIRD_CLIENT_SECRET` / `WEIRD_REFRESH_TOKEN`
- `channel_food` TTS → `ELEVENLABS_API_KEY` (+ 선택 `ELEVENLABS_VOICE_ID`)

`.env`, `*.key`, `client_secret*.json`은 gitignore 대상이다. 커밋 전 `git status`로
스테이징 목록을 확인하고, 파일명이 무해해 보여도 내용을 의심할 것.

## GitHub Actions

`.github/workflows/`의 워크플로 대부분이 **cron으로 실제 채널에 업로드한다.**
스케줄이나 스크립트를 고치면 라이브 발행이 바뀐다. 손대기 전에 확인을 받을 것.

`used_log*.csv`와 `metrics.csv`는 워크플로가 append하는 실행 기록이다. append-only로
다루고 임의로 정리하거나 되돌리지 않는다. `[skip ci]` 커밋 대부분이 이것이다.

## 프로젝트별 불변 규칙

### market-verify

채널은 **머니로직 MoneyLogic**. 이름·소개·면책 문구는 `src/brand.py` 에서만 고친다.
채널은 세 갈래(토크노믹스 / 매크로·유동성 / 수학적 전략 검증)를 다루는데,
이 디렉터리는 세 번째의 일부만 만든다. 채널 전체 파이프라인으로 착각하지 말 것.

`NOTES.md`에 이유까지 적혀 있다. 요약하면:

1. **숫자는 코드가 뽑는다.** LLM은 시계열 수치를 지어낸다. `market_events.py`가
   데이터 블록을 만들고 모델은 그 안의 숫자만 쓴다.
2. **규칙 판정은 `validator.py`만 한다.** 모델에게 자체 점검을 시켰더니 위반해놓고
   통과했다고 답했다. 모델의 자기 보고를 근거로 쓰지 않는다.
3. **`## 6. [운영자 코멘트]`는 비워 둔다.** 사람이 채우는 칸이고, 모델이 채우면
   검증기가 위반으로 잡는다. 이 동작을 완화하지 말 것.
4. **예측·매수매도 추천·목표가를 생성하지 않는다.** 국내 유사투자자문 규제 때문이다.

`apply_min_gap()`의 60거래일 필터와 `summarize()`의 분포(중앙값·최저·최고)는
장식이 아니다. 없으면 대본이 사실과 다른 말을 한다. 지울 때는 이유를 확인할 것.

API 호출은 비용이 든다. 블록만 확인할 때는 `--block-only`를 쓴다.

영상은 `src/produce.py` 가 만든다. 화면 문구는 대본의 `[자료 화면:]` 표기에서
나오므로 따로 짓지 않는다. 업로드 기본값은 **비공개**이고, 공개 전환은 사람이 한다.
`assert_target_channel` 로 엉뚱한 채널에 올라가는 것을 막는다 — 이 저장소는
채널을 여러 개 운영한다.

### channel_food / shorts_engine

컷 계산은 `channel_food/scripts/timeline.py` **한 곳에만** 있고 `shorts_engine`은
재노출만 한다. 두 파이프라인이 다른 컷을 만들지 않게 하려는 것이므로 복제하지 말 것.

채널 이름·핸들·설명문은 `channel_food/scripts/brand.py` 상수에서만 고친다.

## 산출물

`output/`, `out/`은 gitignore다. 생성된 영상·대본·데이터 블록을 커밋하지 않는다.

## 문서와 커밋

문서와 주석은 한국어로 쓴다. 커밋 메시지는 한국어·영어가 섞여 있고 강제 규칙은
없다. 무엇을 바꿨는지보다 **왜 바꿨는지**를 남기는 편이 이 리포의 기존 관행에 맞다.
