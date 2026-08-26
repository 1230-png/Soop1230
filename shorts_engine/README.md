# Shorts Engine

피드백 루프가 들어간 쇼츠 파이프라인. 실적이 나쁜 주제를 다음 생성에서 배제하고,
영상 길이를 나레이션에 맞추며, 첫 3초를 빠른 컷으로 채운다.

**비용 0원.** Ollama(로컬), edge-tts, ffmpeg, PostgreSQL 무료 티어, YouTube 무료 할당량.

---

## 왜 이렇게 배치했나

Ollama는 로컬에서만 돈다. 그런데 발행은 PC가 꺼져 있어도 매일 이어져야 한다.
그래서 **Postgres를 큐로 둔다.**

```
[로컬 PC · 가끔 켜짐]           [무료 클라우드 Postgres]      [GitHub Actions · 24/7]
 Ollama (Llama 3)                      │
 POST /scripts/generate ──INSERT──►  scripts (큐)  ──claim──►  렌더 → 업로드
 POST /metrics/sync    ──────────►  video_metrics ◄──complete── videos
```

PC를 켠 김에 대본 열 편을 만들어 두면, 그 뒤 열흘은 PC 없이 발행된다.

---

## 시작하기

```bash
cd shorts_engine
pip install -r requirements.txt
cp .env.example .env          # DATABASE_URL 등을 채운다

docker compose up -d db       # 로컬 개발용. 배포는 Neon/Supabase
alembic upgrade head
python3 scripts/seed.py       # 카테고리 + 기존 콘텐츠 60편 적재

ollama serve &                # 별도 터미널
ollama pull llama3

uvicorn app.main:app --reload
```

### 대본 만들기 (로컬, Ollama 필요)

```bash
curl -X POST localhost:8000/scripts/generate -H 'Content-Type: application/json' \
     -d '{"count": 10}'
```

### 큐에서 꺼내 렌더링 (Actions, Ollama 불필요)

```bash
python3 scripts/worker.py --out-dir /tmp/out
```

---

## 알고 있어야 할 두 가지

**1. 초기에는 피드백 루프가 아무것도 안 한다.**

판정에는 카테고리당 조회수 500 이상인 영상이 3편 이상 필요하다. 그전까지
제외 목록은 비어 있고 프롬프트에 제외 조건이 붙지 않는다. **버그가 아니다.**

현황은 여기서 확인한다:
```bash
curl localhost:8000/topics/coverage   # enough_data 가 false면 표본 부족
curl localhost:8000/topics/thresholds # 현재 판정 기준
```

**2. 좋아요 비율은 쇼츠에서 후행 지표다.**

노출을 좌우하는 건 시청 지속률이고, 0~3초 빠른 컷이 겨냥하는 것도 그쪽이다.
그래서 Data API(조회수·좋아요·댓글)에 더해 Analytics API의 평균 시청 지속률을
함께 저장한다. **Analytics 스코프가 없으면 지속률만 NULL로 두고 나머지는 정상 수집한다.**

지속률까지 받으려면 refresh token에 `yt-analytics.readonly` 스코프가 필요하다.
없으면 `/metrics/sync` 응답의 `analytics_available`이 `false`로 온다.

---

## 렌더링 로직

`render/timeline.py`의 `build_timeline`이 핵심이다. ffmpeg 의존성이 없는 순수 함수라
단위 테스트로 완전히 고정돼 있다.

- **길이는 나레이션을 따른다.** 30초 고정이 아니다. 문장별 TTS 길이를 ffprobe로 재서 합산한다.
- **첫 3초는 0.5초마다 컷이 바뀐다.** 이 구간만 문장 경계를 무시한다.
  배경은 같은 사진을 조금씩 확대한 변형이라, 정지 이미지인데도 움직이는 것처럼 보인다.
- **3초 이후는 문장 경계를 지킨다.** 화면 문장과 들리는 문장이 어긋나면 안 된다.

MoviePy 대신 ffmpeg를 직접 호출한다. MoviePy는 프레임을 파이썬으로 왕복시켜
같은 결과를 몇 배 느리게, 훨씬 많은 메모리로 만든다.

---

## 테스트

```bash
python3 -m pytest tests/ -q
```

- `test_timeline.py` (24개) — 컷 계산. ffmpeg 불필요, 0.05초
- `test_ollama_contract.py` (23개) — 프롬프트 주입, 깨진 JSON 처리. Ollama 불필요
- `test_render_integration.py` (8개) — 실제 ffmpeg로 영상 생성. TTS만 스텁

통합 테스트가 확인하는 것: 영상이 실제로 만들어지는지, 길이가 나레이션을 따르는지,
첫 3초에 컷이 정확히 6개인지, 디코딩 오류가 없는지, 마지막 컷이 잘리지 않는지.

---

## 주요 설계 판단

| 결정 | 이유 |
|---|---|
| 지표는 append-only 스냅샷 | UPDATE하면 성장 곡선을 잃고, 실패한 수집이 멀쩡한 값을 덮어쓴다 |
| `like_ratio`는 DB 생성 컬럼 | 파이썬에서 계산하면 라우터와 분석 쿼리가 다른 공식을 쓰게 된다 |
| `NULLIF(view_count, 0)` | 조회수 0인 신규 영상에서 0 나눗셈이 나면 수집 잡 전체가 죽는다 |
| 카테고리당 최소 표본 3편 | 없으면 운 나쁜 한 편이 카테고리를 영구히 배제한다 |
| `FOR UPDATE SKIP LOCKED` | 없으면 두 워커가 같은 대본을 렌더해 같은 영상이 두 번 올라간다 |
| `content_hash` UNIQUE | 로컬 LLM은 같은 대본을 반복해서 낸다 |
| 실패한 대본을 pending으로 안 되돌림 | 같은 이유로 계속 실패하면 큐가 막힌다 |
| Ollama 출력을 Pydantic으로 재검증 | `format:"json"`을 줘도 코드펜스·누락 필드가 흔하다 |

---

## 기존 파이프라인과의 관계

`channel_food/`는 그대로 두고 계속 발행한다. 이 엔진이 검증되면
`weird_shorts_publish.yml`을 `scripts/worker.py`로 갈아끼운다. 그때까지 채널 공백은 없다.

`render/media.py`가 `channel_food/scripts/common.py`의 검증된 함수(edge-tts, Pexels 배경,
배경음 합성, mp3 안전 접합)를 그대로 끌어다 쓴다. 600줄을 복제하지 않기 위해서다.
