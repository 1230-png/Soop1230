"""데모: 테스트 데이터로 전체 파이프라인 실행"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

print("\n" + "="*70)
print("🚀 머니로직 파이프라인 - 전체 실행 데모")
print("="*70)

from app.models import Base
from app.database import engine, AsyncSessionLocal
from app.repositories import VideoTaskRepository


async def main():
    # ============= Step 1: DB 초기화 =============
    print("\n[Step 1] 데이터베이스 초기화")
    print("-" * 70)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 데이터베이스 테이블 생성 완료")

    # ============= Step 2: 테스트 작업 생성 =============
    print("\n[Step 2] 테스트 작업 생성")
    print("-" * 70)

    async with AsyncSessionLocal() as session:
        repo = VideoTaskRepository(session)
        task = await repo.create(
            ticker="DEMO",
            target_date="2026-09-05",
            topic="테스트 머니로직 영상"
        )
        task_id = task.id
        print(f"✅ 작업 생성: ID={task_id}, Ticker={task.ticker}")

    # ============= Step 3: 테스트 스크립트 & 오디오 생성 =============
    print("\n[Step 3] 스크립트 및 오디오 생성 (모의 데이터)")
    print("-" * 70)

    output_dir = Path("./test_output/TEST/2026-09-05")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 테스트 MP3 파일 생성 (dummy)
    audio_path = output_dir / "narration.mp3"
    with open(audio_path, 'wb') as f:
        f.write(b'\xff\xfb\x90\x00')  # MP3 sync word
        f.write(b'\x00' * 1000)  # simple MP3 data

    print(f"✅ 오디오 생성: {audio_path}")

    # ============= Step 4: 테스트 비디오 생성 =============
    print("\n[Step 4] 테스트 비디오 생성")
    print("-" * 70)

    try:
        import imageio
        import numpy as np

        video_path = output_dir / "TEST_2026-09-05.mp4"

        # 간단한 프레임 생성 (1920x1080, RGB)
        frames = []
        fps = 30
        duration = 7  # seconds

        # 배경색 (진한 파란색)
        bg_color = np.array([15, 23, 42], dtype=np.uint8)

        for i in range(fps * duration):
            frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            frame[:, :] = bg_color
            frames.append(frame)

        # 비디오 저장
        with imageio.get_writer(str(video_path), fps=fps, codec='libx264') as writer:
            for frame in frames:
                writer.append_data(frame)

        print(f"✅ 비디오 생성: {video_path}")
        print(f"   크기: {video_path.stat().st_size / (1024*1024):.1f} MB")

        # DB 업데이트
        async with AsyncSessionLocal() as session:
            repo = VideoTaskRepository(session)
            await repo.update_audio_path(task_id, str(audio_path))
            await repo.mark_rendered(task_id, str(video_path))
        print(f"✅ DB 업데이트 완료")

    except Exception as e:
        print(f"⚠️  비디오 생성 오류: {e}")
        return

    # ============= Step 5: 작업 상태 확인 =============
    print("\n[Step 5] 최종 작업 상태")
    print("-" * 70)

    async with AsyncSessionLocal() as session:
        repo = VideoTaskRepository(session)
        task = await repo.get_by_id(task_id)
        if task:
            print(f"✅ 작업 ID: {task.id}")
            print(f"   종목: {task.ticker}")
            print(f"   날짜: {task.target_date}")
            print(f"   주제: {task.topic}")
            print(f"   렌더링 완료: {task.is_rendered}")
            if task.video_path:
                print(f"   영상 경로: {task.video_path}")

    # ============= Step 6: YouTube 업로드 (실제 환경에서) =============
    print("\n[Step 6] YouTube 비공개 업로드")
    print("-" * 70)

    youtube_creds = os.getenv("YOUTUBE_CREDENTIALS_JSON")
    if not youtube_creds or not Path(youtube_creds).exists():
        print("⚠️  YouTube 자격증명 설정 필요:")
        print("   1. https://console.cloud.google.com 에서 OAuth 클라이언트 ID 생성")
        print("   2. .env 파일에 설정:")
        print("      YOUTUBE_CREDENTIALS_JSON=/path/to/credentials.json")
        print("      YOUTUBE_TOKEN_JSON=/path/to/token.json")
        print("\n   자격증명이 있으면 다음 코드로 업로드:")
        print("      curl -X POST 'http://localhost:8000/generate?ticker=TEST'")
    else:
        print("✅ YouTube 자격증명 발견")
        print("   → 실제 YouTube API를 통해 비공개 업로드를 시작할 수 있습니다.")

    # ============= 최종 보고서 =============
    print("\n" + "="*70)
    print("📊 파이프라인 실행 완료!")
    print("="*70)

    print("\n🚀 다음 단계:")
    print("-" * 70)
    print("1. FastAPI 서버 실행:")
    print("   export $(cat .env | grep -v '^#' | xargs)")
    print("   python main.py")
    print("\n2. API를 통해 실제 영상 생성 (실제 API 키 필요):")
    print("   curl -X POST 'http://localhost:8000/generate?ticker=AAPL'")
    print("\n3. 작업 상태 확인:")
    print("   curl 'http://localhost:8000/task/1'")
    print("\n4. YouTube 비공개 업로드:")
    print("   - 자격증명 설정 후 자동으로 진행됨")
    print("\n" + "="*70)
    print("✨ 모든 준비가 완료되었습니다!")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
