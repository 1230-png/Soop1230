# 🌘 현실 속 기괴한 현상

현실 속 기괴한 현상을 다루는 YouTube 쇼츠 자동 생성·업로드 파이프라인.
매일 1편, 100% 무료 스택으로 돌아갑니다.

> 처음 설정하거나 인증 오류를 겪고 있다면 **[SETUP.md](SETUP.md)** 를 먼저 보세요.

## 구조

```
channel_food/
├── scripts/
│   ├── brand.py                    채널 이름·핸들·설명문 상수 (여기만 고치면 전체 반영)
│   ├── weird_content.json          콘텐츠 60편
│   ├── common.py                   폰트·팔레트·TTS·앰비언스 합성·업로드 가드
│   ├── timeline.py                 컷 계산 (0~3초 빠른 컷). 순수 함수
│   ├── cta.py                      마지막에 붙는 댓글 유도 질문
│   ├── feedback.py                 실적이 나쁜 주제 판정
│   ├── collect_metrics.py          조회수·좋아요 수집 → metrics.csv
│   ├── generate_weird_video.py     영상 1편 생성
│   ├── upload_weird_video.py       YouTube 업로드
│   ├── update_channel_branding.py  채널 설명문·키워드 적용
│   └── get_refresh_token.py        OAuth refresh token 발급 (로컬 1회)
├── tests/                          pytest (ffmpeg·네트워크 불필요)
├── used_log.csv                    사용 기록 겸 일일 한도 판단 근거
├── metrics.csv                     조회수·좋아요 스냅샷 (append-only)
└── output/                         생성 결과 (gitignore)
```

> 디렉토리 이름이 `channel_food`인 것은 이전 음식 채널에서 이어받았기 때문입니다.
> 워크플로 경로가 여기에 묶여 있어 그대로 두었습니다.

## 콘텐츠

`weird_content.json`의 각 항목은 하나의 영상이 됩니다.

```json
{
  "id": 1,
  "type": "perception",
  "title": "시계 초침이 멈춰 보이는 이유",
  "hook": "첫 화면에 띄울 한 줄",
  "body": ["나레이션 문장들", "..."],
  "twist": "마지막에 남기는 한 줄",
  "ambience": ["low_drone", "heartbeat"],
  "hashtags": ["#크로노스타시스"]
}
```

`hook` + `body` 각 문장 + `twist` + **댓글 유도 질문**이 각각 한 화면이 됩니다.
질문은 `cta.py`가 주제에 맞춰 붙이고, 항목에 `"cta"`를 직접 써 두면 그것을 씁니다.

각 문장의 나레이션 길이를 `ffprobe`로 재서 표시 시간으로 쓰므로,
**화면의 문장과 들리는 문장이 항상 일치합니다.** 길이도 30초 고정이 아니라
나레이션을 따라갑니다.

### 앞 3초는 0.5초마다 끊긴다

쇼츠 이탈은 대부분 앞 3초에서 납니다. 이 구간만 문장 경계를 무시하고
0.5초마다 화면을 바꿉니다 (`timeline.py`). 배경은 같은 사진을 조금씩 확대한
변형이라, 정지 이미지인데도 밀려 들어오는 것처럼 보입니다.

3초 이후는 문장 경계를 지킵니다. `HOOK_SEC` / `HOOK_CUT` 환경변수로 조절합니다.

## 피드백 루프

```
발행 → collect_metrics.py → metrics.csv → feedback.py → 다음 주제 선택
```

매일 발행 직전에 지금까지 올린 영상의 조회수·좋아요를 받아 `metrics.csv`에
쌓고, 주제별 평균 좋아요 비율을 봅니다. 실적이 나쁜 주제는 다음 편에서 건너뜁니다.

판정 기준 세 가지, 전부 오판을 막기 위한 것입니다:

| 기준 | 값 | 없으면 생기는 일 |
|---|---|---|
| 조회수 하한 | 500 | 노출이 안 된 영상의 좋아요 0이 주제 탓으로 기록된다 |
| 주제당 최소 표본 | 3편 | 운 나쁜 한 편이 주제 하나를 영구히 배제한다 |
| 평균으로 판정 | 1% 미만 | 최솟값을 보면 같은 이유로 무너진다 |

**초기에는 아무것도 배제하지 않습니다.** 조회수 500 이상인 영상이 주제당
3편 모일 때까지 제외 목록은 비어 있고, 예전처럼 id 순서대로 나갑니다. 정상입니다.

지금 상태는 이렇게 봅니다:

```bash
python3 channel_food/scripts/feedback.py
```

제외하고 나면 남는 콘텐츠가 없는 경우에는 그냥 발행합니다.
피드백은 순서를 바꾸는 장치이지 발행을 세우는 장치가 아닙니다.

### 왜 DB가 아니라 CSV인가

하루 1편이면 1년에 365행입니다. Postgres를 세울 규모가 아니고, 무료 티어라도
가입·접속 문자열·유휴 정지 같은 사람이 개입할 지점이 생깁니다. CSV는 저장소에
그대로 커밋되므로 로컬과 Actions가 같은 파일을 봅니다.

규모가 커질 때를 대비한 DB 버전(FastAPI + PostgreSQL + Ollama 큐)은
`shorts_engine/`에 그대로 있습니다. 영상 품질에 관여하는 부분(컷 계산·질문·배경)은
이미 이쪽으로 옮겨 왔습니다.

## 테스트

```bash
python3 -m pytest channel_food/tests/ -q
```

ffmpeg도 네트워크도 필요 없습니다. 컷 계산, 주제 판정, 배경 변형만 봅니다.

`type`은 `perception`(지각 현상) / `mandela`(만델라 효과) / `unexplained`(미해결) /
`urban_legend`(도시전설). 선택은 무작위가 아니라 **아직 안 쓴 것 중 가장 작은 id** 순서입니다.

### 콘텐츠를 추가할 때

사실관계를 단정하는 문장은 피하세요. 검증된 현상은 그대로 서술하되,
가설 단계인 것은 "~라는 설명이 있습니다", "아직 정설은 아닙니다"처럼 남겨 두는 편이 좋습니다.

## 오디오

**`narration`(나레이션 전용)으로 확정했습니다.** 별도로 설정할 것은 없습니다.

`AUDIO_MODE` 환경변수로 바꿀 수 있지만, 두 값 모두 기본값이 `narration`이라
그냥 두면 나레이션만 나옵니다.

| 값 | 내용 |
|---|---|
| `narration` (**확정된 기본값**) | edge-tts 한국어 나레이션만 |
| `narration_ambience` (대안) | 나레이션 + 불길한 배경음 (`ambience` 필드 기준). 워크플로 수동 실행에서 골라 볼 수 있게 남겨 뒀습니다 |

배경음 4종은 모두 ffmpeg로 실시간 합성합니다. 음원 파일도, 저작권도, API 키도 없습니다.

| 이름 | 소리 |
|---|---|
| `low_drone` | 45Hz 사인 + 브라운 노이즈. 낮게 깔리는 지속음 |
| `heartbeat` | 60Hz를 72bpm으로 맥동 |
| `wind_howl` | 핑크 노이즈 밴드패스. 바람이 새는 소리 |
| `static_hiss` | 화이트 노이즈 하이패스. 오래된 녹음 질감 |

배경음은 나레이션 대비 18% 볼륨(`common.AMBIENCE_GAIN`)으로 깔려 말소리를 덮지 않습니다.

## 로컬에서 돌려보기

```bash
cd channel_food/scripts
pip install -r requirements.txt

# 오늘 몫을 이미 썼어도 강제로 만들어 보려면 SKIP_DAILY_GUARD=1
SKIP_DAILY_GUARD=1 AUDIO_MODE=narration_ambience python3 generate_weird_video.py
```

결과는 `channel_food/output/`에 `weird_shorts_<id>.mp4`로 나옵니다.

## 자동 실행

| 워크플로 | 시점 |
|---|---|
| [쇼츠 생성·업로드](../.github/workflows/weird_shorts_publish.yml) | 매일 06:00 KST + 수동 |
| [채널 설명·키워드](../.github/workflows/channel_branding.yml) | 수동 전용 |

## 안전장치

하루 1편(`MAX_DAILY_UPLOADS`)을 **생성 단계와 업로드 단계에서 각각** 확인합니다.
생성 단계에서 먼저 막는 이유는 GitHub Actions 실행 시간을 아끼기 위해서고,
업로드 단계에서 한 번 더 보는 이유는 수동 실행 연타를 막기 위해서입니다.

자세한 내용과 문제 해결은 [SETUP.md](SETUP.md)에 있습니다.
