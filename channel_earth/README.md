# channel_earth — 「지구의 오늘」

공공 API 의 관측값을 그대로 지도에 찍는 채널. 음성 합성도 배경음악도 쓰지
않는다. 화면과 소리 전부 자료에서 계산해 만든다.

```bash
# 숏폼 (세로 9:16, 약 52초)
python3 channel_earth/build.py --window day

# 롱폼 (가로 16:9) — 같은 자료로 한 주치를 길게
python3 channel_earth/build.py --window week --size 1920x1080 --lapse 300

# 네트워크 없이 렌더만 확인 (가짜 데이터, 발행 불가 표시가 박힌다)
python3 channel_earth/build.py --cache data/fixtures/usgs_day_synthetic.json

cd channel_earth && python3 -m pytest      # 네트워크 안 탄다
```

## ⚠ 실제 API 응답을 확인하지 못했다

**이 코드를 만든 컨테이너에서 USGS 에 닿지 못했다.** 조직의 egress 정책이
`earthquake.usgs.gov`, `api.nasa.gov`, `api.open-meteo.com` 으로 나가는
CONNECT 를 전부 403 으로 막는다(프록시 로그로 확인).

그래서 `lib/sources.py` 의 파서는 **USGS 가 문서로 공개한 GeoJSON 스키마를
보고 쓴 것이지, 실제 응답을 보고 쓴 것이 아니다.** GitHub Actions 에는 그
제한이 없으므로 거기서는 돌지만, **첫 실행은 반드시 이렇게 할 것:**

```bash
python3 channel_earth/build.py --window day --dump data/first_response.json
```

`--dump` 가 응답을 그대로 떨어뜨린다. 그 파일을 눈으로 확인하기 전까지는
발행하지 말 것. 파서는 형식이 달라도 죽지 않고 **몇 줄을 버렸는지 찍으며**,
한 줄도 못 읽으면 멈춘다 — 조용히 빈 지도가 도는 영상이 나오는 것이 제일
나쁘기 때문이다.

## 가짜 데이터가 발행되지 않게

`tools/make_fixture.py` 가 렌더 확인용 가짜 지진을 만든다. 실제 지진대 위에
구텐베르크-리히터 분포로 뿌려 **닮게** 만들지만 전부 지어낸 숫자다.

지진 정보를 사실처럼 내보내는 것은 다른 실수와 무게가 다르므로 경로를 막아
뒀다. 파일 이름에 `synthetic` 이 들어간 캐시로 만든 빌드는 metadata 에
`synthetic: true` 가 박히고, `build.verify_publishable` 이 그것을 보고
멈춘다. `upload.py` 도 올리기 직전에 같은 함수를 부른다.
`tests/test_publish_gate.py` 가 그 경로를 지킨다.

## 화면

| 파일 | 하는 일 |
|---|---|
| `lib/sources.py` | USGS 피드 받기·파싱. 못 읽는 줄은 버리고 개수를 찍는다 |
| `lib/render.py` | 지도·점·고리·범례·막대. PIL 이 아니라 numpy 로 |
| `lib/audio.py` | 지진 하나가 소리 하나. 높이는 깊이가, 크기는 규모가 |
| `build.py` | 프레임을 ffmpeg 로 흘려보내고 소리와 합친다 |
| `upload.py` | `EARTH_*` 전용. 대체 자격 증명 없음 |
| `assets/` | NASA Blue Marble (1920×960 으로 줄여 저장소에 넣었다) |

### 왜 MoviePy 가 아닌가

MoviePy 는 결국 ffmpeg 래퍼인데, 프레임을 직접 만들어 내는 이 작업에서는
중간 계층이 느리기만 하고 얻는 것이 없다. numpy 배열을 ffmpeg 표준 입력으로
그대로 흘려보낸다 — `channel_sim` 에서 22,000프레임으로 확인한 방식이다.

### 세 겹으로 나눠 그린다

1. **바탕** — 지구 사진과 눈금. 한 번 만들고 복사만 한다
2. **쌓이는 층** — 이미 일어난 지진의 점. 새로 생긴 것만 더한다
3. **퍼지는 층** — 방금 일어난 지진의 고리. 매 프레임 다시 그리지만 한두 개다

점을 **덮지 않고 더하는** 이유: 같은 자리에서 지진이 여러 번 나면 그 자리가
밝아져야 한다. 덮어쓰면 열 번 난 곳과 한 번 난 곳이 똑같이 보이는데,
지도에서 제일 말하고 싶은 것이 그 차이다.

### 지도에서 잘라 낸 것

위도 -65~80 만 쓴다. 남극 대륙이 새하얘서 그대로 두면 화면에서 제일 밝은
덩어리가 되는데 정작 지진은 거의 없다. 잘린 위도의 지진은 **숫자에는 넣되
지도에는 그리지 않는다** — 건수가 어긋나면 막대 합과 누적 건수가 안 맞는다.

## 숏폼과 롱폼을 같이 뽑는 이유

**숏폼 시청 시간은 파트너 프로그램의 3,000시간에 집계되지 않는다.** 앞
채널이 61일 동안 숏츠로 13,848회를 모으고도 시청 시간 기여가 사실상 0이었다.
숏폼은 도달에, 롱폼은 시청 시간에 쓴다. `Layout` 이 화면 크기에서 자리를
계산하므로 렌더러는 한 벌이다.

## 비밀값

**환경변수로만. 코드·커밋·로그에 절대 넣지 않는다.**

`EARTH_CLIENT_ID` / `EARTH_CLIENT_SECRET` / `EARTH_REFRESH_TOKEN` /
`EARTH_CHANNEL_ID`.

**대체 경로를 두지 않는다.** `longform/upload.py:40` 은 `Y3B_*` 가 비면 공용
`YT_*` 로 넘어가는데, 시크릿을 깜빡한 날 남의 채널로 조용히 올라간다.
유튜브 일일 할당량도 채널이 아니라 **구글 클라우드 프로젝트 단위**라
돌려쓰면 서로의 몫을 깎는다 — 이 채널은 제 프로젝트를 쓴다.

USGS 는 키가 필요 없다. 뒤에 붙일 NASA NeoWs 는 무료 키가 필요하고,
그때 `NASA_API_KEY` 가 하나 늘어난다.

## 아직 없는 것

- **cron 워크플로.** 실제 응답을 한 번도 못 봤으므로 아직 걸지 않는다.
  `--dump` 로 한 번 확인한 뒤에 건다
- NASA 소행성·NOAA 우주기상 소스 (`channel.yaml` 의 `sources` 에 목록만)
- 썸네일. 지금은 유튜브가 고른 프레임을 쓴다
