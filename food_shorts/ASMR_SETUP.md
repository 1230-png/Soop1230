# 무료 소스 설정 가이드

영상과 효과음을 **전부 무료로** 수급합니다. 유료 구독이나 결제가 필요한
API는 쓰지 않습니다.

---

## 1. 어디서 가져오나

| 종류 | 소스 | 키 필요? | 비용 |
|---|---|---|---|
| 영상 | Pixabay | 무료 가입 | 무료 |
| 영상 | Pexels | 무료 가입 | 무료 |
| 영상 | Wikimedia Commons | **불필요** | 무료 |
| 효과음 | Freesound | 무료 가입 | 무료 |
| 효과음 | Wikimedia Commons | **불필요** | 무료 |

**키가 하나도 없어도 Commons 로 동작합니다.** 다만 Commons 는 요리 영상이
많지 않아, 키를 등록하면 소스 폭이 훨씬 넓어집니다.

---

## 2. 무료 키 등록 (권장, 약 5분)

셋 다 **무료 가입만** 하면 되고 카드 등록이 없습니다.

| 사이트 | 주소 |
|---|---|
| Pixabay | https://pixabay.com/api/docs/ |
| Pexels | https://www.pexels.com/api/ |
| Freesound | https://freesound.org/apiv2/apply/ |

키를 받은 뒤 GitHub 저장소에서:

**Settings → Secrets and variables → Actions → New repository secret**

| Name | Secret |
|---|---|
| `PIXABAY_API_KEY` | Pixabay 키 |
| `PEXELS_API_KEY` | Pexels 키 |
| `FREESOUND_API_KEY` | Freesound 키 |

하나만 넣어도 되고, 셋 다 넣으면 가장 좋습니다.

---

## 3. 영상 구성

한 편은 타이틀 + 3단계, 총 4장면입니다.

| 장면 | 길이 | 내용 |
|---|---|---|
| 타이틀 | 2.8초 | 요리 제목 + 후킹 문구 |
| STEP 1 | 3.4초 | 손질/준비 (칼질 등) |
| STEP 2 | 3.4초 | 조리 (지글지글, 소스 붓기) — **0.75배속** |
| STEP 3 | 3.4초 | 완성 (김 모락모락) |

교차 전환으로 겹치는 1.2초를 빼면 **약 11.8초**입니다.

STEP 2 만 느리게 재생됩니다. 요리 영상에서 가장 잘 먹히는 장면이
소스 붓기·지글거림이라, 시간을 늘려 보여주는 연출입니다.

---

## 4. 검색어 바꾸기

`data/food_list.json` 에서 영상·효과음 검색어를 정합니다.
Pixabay·Freesound 는 영어로 색인되어 있어 **영어로 써야** 결과가 나옵니다.

```json
{
  "clip_query": "cooking eggs frying pan",
  "sound_query": "frying pan sizzle",
  "steps": [
    {
      "text": "달군 팬에 기름 두르면 지글지글",
      "ingredient": "식용유 1T",
      "sound": "기름",
      "clip_query": "egg cooking sizzling frying pan",
      "sound_query": "frying sizzle pan"
    }
  ]
}
```

**중요**: `clip_query` 는 **동작**을 노려야 합니다.

| 좋음 | 나쁨 |
|---|---|
| `chopping vegetables knife cutting board` | `vegetables` |
| `deep frying oil bubbling closeup` | `fried food` |
| `pouring sauce into pan` | `sauce` |

정지된 접시 사진 같은 영상이 잡히면 검색어에 동작 단어
(`chopping`, `pouring`, `sizzling`, `boiling`, `stirring`)를 넣으세요.

---

## 5. 직접 찍은 영상/소리 넣기

인터넷 소스보다 **항상 우선**합니다.

| 폴더 | 파일명 |
|---|---|
| `assets/clips/` | `3_title.mp4`, `3_step1.mp4` … |
| `assets/sounds/` | 파일명에 `기름`, `국물`, `채소` 등 큐가 들어가면 자동 매칭 |

자세한 규칙은 각 폴더의 `README.md` 참고.

---

## 6. 효과음 큐

`sound` 에 지정합니다. 쉼표로 여러 개 겹칠 수 있습니다.

| 큐 | 소리 |
|---|---|
| `기름` | 밝고 빠른 지글지글 |
| `고기` | 묵직한 지글지글 |
| `국물` | 낮고 둥근 보글보글 |
| `불` | 넓게 퍼지는 끓는 소리 |
| `채소` | 또각또각 칼질 |
| `계란` | 톡 깨지는 소리 |
| `소스` | 가늘게 흐르는 소리 |
| `김` | 은은한 스팀 (항상 자동으로 깔림) |

인터넷에서 효과음을 못 받으면 **ffmpeg 가 이 큐대로 소리를 합성**합니다.
합성도 100% 무료이고 키가 필요 없습니다.

---

## 7. 영상을 못 구하면?

**정지 이미지로 대체하지 않고 실행을 중단합니다.**

슬라이드쇼 같은 영상이 채널 이름으로 올라가는 것보다 안 올리는 게 낫기
때문입니다. 로그에 어느 장면에서 실패했는지와 해결 방법이 찍힙니다.

해결 순서:
1. 무료 키를 등록했는지 확인
2. `clip_query` 를 더 일반적인 단어로 (예: `frying pan` 만 남기기)
3. `assets/clips/` 에 직접 찍은 영상 넣기

---

## 8. 라이선스

| 소스 | 조건 |
|---|---|
| Pixabay | 상업적 이용 무료, 출처 표기 불필요 |
| Pexels | 상업적 이용 무료, 출처 표기 불필요 |
| Freesound | 대부분 CC0/CC-BY — **CC-BY 는 출처 표기 필요** |
| Wikimedia Commons | 대부분 CC-BY/CC-BY-SA — **출처 표기 필요** |

영상 설명에 출처 문구가 자동으로 들어갑니다. Freesound·Commons 소재를
쓸 때는 개별 저작자 표기가 필요할 수 있으니, 수익화 전에 한 번 확인하세요.

---

## 9. 테스트

```bash
cd food_shorts/scripts
PIXABAY_API_KEY=... FREESOUND_API_KEY=... python3 generate_video.py
```

생성 위치: `food_shorts/output/generated/`
