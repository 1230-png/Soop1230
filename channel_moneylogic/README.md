# 머니로직 (MoneyLogic) Channel

경제/재정 교육 콘텐츠 자동 생성 채널.

## 구조

- `scripts/`: 영상 생성 스크립트
  - `visuals.py`: Pillow를 이용한 UI 요소 생성 (타이틀, 자막, 워터마크 등)
  - `render.py`: moviepy를 이용한 최종 영상 렌더링
  - `smoke_test_render.py`: 렌더링 검증용 테스트 스크립트

## 사용법

### 스모크 테스트 (렌더링 검증)

```bash
cd scripts
python smoke_test_render.py
```

이 명령은 가짜 오디오와 차트로 실제 mp4를 생성합니다.
- `smoke/test.mp4`: 생성된 영상
- `smoke/frame_*.png`: 주요 시점 스냅샷

## 의존성

- `pillow`: 이미지 생성
- `moviepy`: 영상 렌더링
- `numpy`: 배열 처리
- `imageio-ffmpeg`: FFmpeg 바이너리
- `decorator<5.0`: moviepy 1.0.3 호환성
