"""전체 파이프라인 테스트 스크립트.

로컬에서 DB 없이 각 단계를 검증한다.
"""

import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# app 모듈 경로 추가
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app.config import get_settings
from app.services.script_generator import generate_complete_script
from app.services.tts import synthesize_timeline


async def test_script_generation():
    """Step 2 테스트: 스크립트 생성"""
    print("\n" + "="*60)
    print("📝 [테스트 1] 스크립트 생성 (yfinance + OpenAI)")
    print("="*60)

    ticker = "AAPL"
    try:
        script_data = await generate_complete_script(ticker)

        print(f"\n✅ 스크립트 생성 성공!")
        print(f"   주제: {script_data['topic']}")
        print(f"   총 길이: {script_data['total_duration']:.1f}초")
        print(f"   세그먼트 수: {len(script_data['timeline'])}")

        print("\n📋 타임라인:")
        for i, seg in enumerate(script_data['timeline'], 1):
            print(f"   {i}. [{seg['start']:.1f}s ~ {seg['start'] + seg['duration']:.1f}s]")
            print(f"      키워드: {seg['keyword']}")
            print(f"      텍스트: {seg['text'][:50]}...")

        return script_data

    except Exception as e:
        print(f"❌ 실패: {str(e)}")
        return None


async def test_tts_synthesis(script_data):
    """Step 3 테스트: TTS 음성 합성"""
    print("\n" + "="*60)
    print("🎤 [테스트 2] TTS 음성 합성 (edge-tts / ElevenLabs)")
    print("="*60)

    settings = get_settings()
    output_dir = Path("./test_output/audio")

    try:
        timeline = script_data['timeline']

        print(f"\n🔊 TTS 모드: {'ElevenLabs' if settings.environment == 'production' else 'edge-tts'}")
        print(f"   출력 디렉토리: {output_dir}")

        audio_path, updated_timeline = await synthesize_timeline(timeline, output_dir)

        print(f"\n✅ TTS 합성 성공!")
        print(f"   오디오: {audio_path}")
        print(f"   파일 크기: {audio_path.stat().st_size / (1024*1024):.2f} MB")
        print(f"   총 길이: {sum(s['duration'] for s in updated_timeline):.1f}초")

        return audio_path, updated_timeline

    except Exception as e:
        print(f"❌ 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None


async def test_video_rendering(ticker, topic, target_date, audio_path, timeline):
    """Step 4 테스트: 영상 렌더링"""
    print("\n" + "="*60)
    print("🎬 [테스트 3] 영상 렌더링 (moviepy)")
    print("="*60)

    from app.services.video_renderer import render_video

    output_dir = Path("./test_output/video")

    try:
        video_path = output_dir / f"{ticker}_{target_date}.mp4"

        print(f"\n   출력 경로: {video_path}")
        print(f"   해상도: 1920x1080")
        print(f"   FPS: 30")

        result = await render_video(
            audio_path=audio_path,
            output_path=video_path,
            ticker=ticker,
            topic=topic,
            date_str=target_date,
            timeline=timeline,
        )

        print(f"\n✅ 렌더링 완료!")
        print(f"   파일: {result}")
        print(f"   크기: {result.stat().st_size / (1024*1024):.2f} MB")

        return result

    except Exception as e:
        print(f"❌ 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def test_youtube_upload(video_path, ticker, topic, target_date):
    """Step 5 테스트: YouTube 업로드"""
    print("\n" + "="*60)
    print("📤 [테스트 4] YouTube 업로드")
    print("="*60)

    from app.services.youtube_uploader import upload_video

    try:
        print(f"\n   영상: {video_path}")
        print(f"   제목: [{ticker}] {topic}")
        print(f"   공개 범위: 비공개")

        # YouTube 업로드
        video_id = await upload_video(
            video_path=video_path,
            title=f"[{ticker}] {topic}",
            description=f"머니로직 - 재무 분석\n{topic}\n\n방송일: {target_date}",
            tags=[ticker, "재무분석", "주식", "경제", "머니로직"],
            is_private=True,
        )

        print(f"\n✅ 업로드 성공!")
        print(f"   비디오 ID: {video_id}")
        print(f"   링크: https://www.youtube.com/watch?v={video_id}")

        return video_id

    except Exception as e:
        print(f"❌ 실패: {str(e)}")
        print(f"   (YouTube 자격증명이 없으면 정상입니다)")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """전체 파이프라인 테스트"""
    print("\n" + "█"*60)
    print("█  머니로직 파이프라인 전체 테스트")
    print("█"*60)

    settings = get_settings()
    ticker = "AAPL"
    target_date = "2024-09-05"

    print(f"\n⚙️  환경 설정:")
    print(f"   환경: {settings.environment}")
    print(f"   종목: {ticker}")
    print(f"   날짜: {target_date}")

    # Step 1: 스크립트 생성
    script_data = await test_script_generation()
    if not script_data:
        print("\n❌ 테스트 중단 (스크립트 생성 실패)")
        return

    # Step 2: TTS 음성 합성
    audio_path, timeline = await test_tts_synthesis(script_data)
    if not audio_path:
        print("\n❌ 테스트 중단 (TTS 합성 실패)")
        return

    # Step 3: 영상 렌더링
    video_path = await test_video_rendering(
        ticker,
        script_data['topic'],
        target_date,
        audio_path,
        timeline,
    )
    if not video_path:
        print("\n❌ 테스트 중단 (렌더링 실패)")
        return

    # Step 4: YouTube 업로드 (선택사항)
    if os.getenv("YOUTUBE_CREDENTIALS_JSON"):
        await test_youtube_upload(video_path, ticker, script_data['topic'], target_date)
    else:
        print("\n" + "="*60)
        print("📤 [테스트 4] YouTube 업로드")
        print("="*60)
        print(f"\n⏭️  YouTube 자격증명이 없으므로 건너뜁니다")
        print(f"   (YOUTUBE_CREDENTIALS_JSON 환경 변수 필요)")

    print("\n" + "█"*60)
    print("█  ✅ 모든 테스트 완료!")
    print("█"*60)
    print(f"\n📁 생성된 파일:")
    print(f"   오디오: {audio_path}")
    print(f"   영상: {video_path}")
    print(f"\n✨ 파이프라인이 정상 작동합니다!")


if __name__ == "__main__":
    asyncio.run(main())
