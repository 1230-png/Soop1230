# channel_rush22 — 「머니러시」 @Rush22

하루 30초, 돈이 되는 생활경제 상식 쇼츠를 **하루 2편 완전 자동**으로 발행합니다.
채널: https://www.youtube.com/@Rush22-i8p

무료 스택만 씁니다 — Pillow, edge-tts, ffmpeg, GitHub Actions, YouTube Data API.
결제 수단을 등록해야 하는 구간이 없습니다.

## 문서

| 문서 | 내용 |
|---|---|
| [`SETUP.md`](SETUP.md) | 시크릿 등록, 첫 실행, 콘텐츠 추가 방법 |
| [`ROADMAP.md`](ROADMAP.md) | 5개월 수익화 계획과 그 한계 |

## 구성

```
scripts/
  common.py            렌더링 · TTS · ffmpeg 합성
  generate_video.py    한 편 생성 후 업로드 (진입점)
  upload_video.py      YouTube 업로드 + 채널 소유 확인
  validate_bank.py     콘텐츠 뱅크 검사
  get_refresh_token.py OAuth 토큰 발급 (로컬 1회)
  content_bank.json    콘텐츠 60편 ← 주제를 바꾸려면 이 파일만 교체
used_log.csv           발행 기록 (자동 커밋)
```

발행 주기는 [`../.github/workflows/run_rush22.yml`](../.github/workflows/run_rush22.yml)에
있습니다.

## 빠른 확인

```bash
python scripts/validate_bank.py              # 콘텐츠 뱅크 검사
python scripts/generate_video.py --dry-run   # 업로드 없이 영상만 생성
```

## 한 편의 구조

`hook`(3~5초) → `body`(15~20초) → `punch`(5~8초) 세 장면이 각각 다른 배경으로
렌더링돼 이어붙습니다. 편당 25~33초입니다.
