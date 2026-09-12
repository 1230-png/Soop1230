# 롱폼 파이프라인 (@200-y3b)

숏츠와 **완전히 독립**된 롱폼 발행 파이프라인입니다. 파일도 상태도 공유하지
않으므로, 이쪽이 망가져도 숏츠는 그대로 돌아갑니다.

## 왜 만들었나

YouTube 파트너 프로그램의 **유효 공개 시청 시간 3,000시간**에는 Shorts 시청
시간이 집계되지 않습니다. 숏츠를 아무리 올려도 그 숫자는 0에서 움직이지
않습니다. 나머지 경로인 Shorts 조회수 300만 회는 90일간 하루 33,000회라
계획으로 세울 수 있는 숫자가 아닙니다.

**롱폼이 유일한 경로입니다.** 이 디렉토리의 목적은 그것 하나입니다.

## 팩 5종

| id | 이름 | 길이 | 표현 수 | 발행 (KST) |
|---|---|---|---|---|
| `weekly_review` | 주간 복습 몰아듣기 | 12분 | 7 | 매주 일 06:00 |
| `shadowing_drill` | 쉐도잉 트레이닝 | 28분 | 25 | 매주 월 06:00 |
| `situation_pack` | 상황별 표현 팩 | 35분 | 30 | 매주 수 06:00 |
| `sleep_english` | 수면 영어 | 62분 | 60 | 격주 금 06:00 |
| `monthly_master` | 월간 총정리 | 70분 | 60 | 매월 말 06:00 |

### shadow_gap — 이 설계의 핵심

레시피 스텝 중 `shadow_gap` 은 **직전 영어 음성 길이 + 0.7초**만큼의 무음이고,
화면에는 "따라 말해보세요"가 뜹니다.

무음이지만 **시청은 계속되므로 시청 시간이 그대로 쌓입니다.** 시청자는 그동안
실제로 소리 내어 따라 하므로 학습 효과도 같이 올라갑니다. 분량 때우기가 아니라
이 파이프라인이 존재하는 이유에 직결된 장치입니다.

## 실행

```bash
# 표현 데이터 만들기 (숏츠 큐에서 변환, 원본은 건드리지 않음)
python3 longform/import_queue.py

# 빌드
python3 longform/build.py --pack weekly_review

# 네트워크 없이 파이프라인만 검증 (TTS 대신 무음, used.json 갱신 안 함)
python3 longform/build.py --pack weekly_review --offline --limit 6

# 업로드
python3 longform/upload.py --dir longform/build/2026-09-13-weekly_review
```

산출물은 `build/<날짜>-<팩>/` 에 `video.mp4`, `metadata.json`, `thumbnail.png`
로 떨어집니다. `metadata.json` 의 `description` 에는 `0:00` 부터 시작하는 챕터
타임스탬프가 들어갑니다.

## 구성

```
packs.yaml         팩 5종 레시피 (음성·속도·해상도 기본값 포함)
build.py           메인 파이프라인
upload.py          YouTube 업로드 (resumable + 채널 검증)
import_queue.py    숏츠 큐 → data/phrases.json
lib/tts.py         edge-tts 래퍼 (해시 캐시 + 3회 재시도 + --offline)
lib/cards.py       PIL 카드 렌더러
data/phrases.json  표현 데이터 (364개, topic 포함)
data/used.json     팩별 소재 사용 이력 — 워크플로가 자동 커밋
```

## 인증

`Y3B_CLIENT_ID` / `Y3B_CLIENT_SECRET` / `Y3B_REFRESH_TOKEN` 을 우선 읽고,
없으면 `YT_*` 로 폴백합니다.

이 저장소의 `YT_*` 는 다른 채널과 공유되며 한 번 교체되면서 이쪽 업로드를
깨뜨린 적이 있습니다. `Y3B_*` 가 @200-y3b 전용 슬롯입니다. 업로드 직전
채널 ID(`UCeXsmdfyW4hoxgWV2K8EwFw`)를 확인하고, 다르면 중단합니다.

시크릿이 없으면 워크플로가 업로드 대신 **월별 릴리스**에 mp4·metadata·썸네일을
올립니다. 스튜디오에서 직접 예약 발행하시면 됩니다.

## 비용

전부 무료입니다. edge-tts(API 키 불필요), PIL, ffmpeg, GitHub Actions 무료 티어.
70분 영상도 정지 카드 + 오디오 복사 방식이라 러너에서 수 분 안에 인코딩됩니다.

## 알아둘 것

- **이모지를 쓰지 마세요.** 러너 폰트에 글리프가 없어 두부(□)로 렌더됩니다.
- concat demuxer는 마지막 항목의 `duration` 을 무시하므로, 마지막 이미지를
  `duration` 없이 한 번 더 적어야 끝 장면이 잘리지 않습니다 (`build.py` 참고).
- `--offline` 은 `used.json` 을 갱신하지 않습니다. 테스트가 다음 실제 발행의
  소재를 소진시키면 안 되기 때문입니다.
