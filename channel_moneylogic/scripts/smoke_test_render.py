"""render.py 스모크 테스트.

TTS나 OpenAI를 건드리지 않고, 가짜 무음 오디오와 가짜 차트 PNG로 실제 mp4를
뽑아 본다. 렌더링 코드만 따로 검증하고 싶을 때 쓴다 -- 크레딧이 들지 않는다.

    python smoke_test_render.py

smoke/ 폴더에 test.mp4와 주요 시점 프레임 PNG가 생성된다.
"""
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

FF = imageio_ffmpeg.get_ffmpeg_exe()
out = Path("smoke"); out.mkdir(exist_ok=True)

# 1) 20초짜리 무음 오디오
audio = out / "narration.mp3"
subprocess.run([FF, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", "20", "-q:a", "9", str(audio)], check=True, capture_output=True)

# 2) chart.py를 흉내낸 차트 PNG (다크테마 #0F172A, 목표 크기로 직접 생성)
chart = Image.new("RGB", (1100, 560), (15, 23, 42))
d = ImageDraw.Draw(chart)
d.rectangle([0, 0, 1099, 559], outline=(51, 65, 85), width=2)
pts = [(60 + i * 20, 460 - (i * 7 % 300)) for i in range(50)]
d.line(pts, fill=(56, 189, 248), width=4)
chart_path = out / "chart.png"; chart.save(chart_path)

# 3) timeline — text 포함(자막 켜짐)
timeline = [
    {"keyword": "서비스 매출", "start": 2.0, "duration": 9.0,
     "text": "애플의 서비스 부문은 하드웨어보다 마진이 높고, 매 분기 반복적으로 발생하는 구조입니다."},
    {"keyword": "마진 변화", "start": 12.0, "duration": 6.5,
     "text": "이 구조가 전체 영업이익률에 어떤 영향을 주는지 보겠습니다."},
]

import render
result = render.build_video(
    audio_path=audio, out_path=out / "test.mp4",
    ticker="AAPL", topic="애플 서비스 매출 구조와 마진 변화",
    date_str="2026년 9월 5일", timeline=timeline, chart_path=chart_path,
)
print("렌더링 완료:", result, result.stat().st_size, "bytes")

# 4) 주요 시점 프레임 추출
for label, ts in [("t02_title", 2.0), ("t06_chart", 6.0), ("t14_second", 14.0), ("t21_outro", 21.0)]:
    subprocess.run([FF, "-y", "-ss", str(ts), "-i", str(result), "-frames:v", "1",
                    str(out / f"frame_{label}.png")], check=True, capture_output=True)
print("프레임 추출 완료")
