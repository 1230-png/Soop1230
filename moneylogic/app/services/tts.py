"""환경별 TTS (Text-to-Speech) 모듈.

- development: edge-tts (완전 무료, API 키 불필요)
- production: ElevenLabs (유료, 프리미엄 음질)
"""

import asyncio
import os
from pathlib import Path

import edge_tts
from elevenlabs import ElevenLabs, VoiceSettings
from elevenlabs.client import ElevenLabs as ElevenLabsClient

from app.config import get_settings


async def synthesize_with_edge_tts(text: str, output_path: Path) -> float:
    """Microsoft edge-tts로 음성 합성 (무료).

    Args:
        text: 합성할 텍스트
        output_path: 저장할 MP3 파일 경로

    Returns:
        음성 길이 (초)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    communicate = edge_tts.Communicate(text, "ko-KR-SunHiNeural")
    await communicate.save(str(output_path))

    # 음성 길이 추정 (한글 텍스트 길이 기반)
    # 평균 음성 속도: 한글 5-6글자 ≈ 1초
    estimated_duration = len(text) / 5.5

    return max(estimated_duration, 1.0)


async def synthesize_with_elevenlabs(text: str, output_path: Path) -> float:
    """ElevenLabs API로 음성 합성 (프리미엄).

    Args:
        text: 합성할 텍스트
        output_path: 저장할 MP3 파일 경로

    Returns:
        음성 길이 (초)
    """
    settings = get_settings()

    if not settings.elevenlabs_api_key:
        raise ValueError("ELEVENLABS_API_KEY가 설정되지 않았습니다.")

    if not settings.elevenlabs_voice_id:
        raise ValueError("ELEVENLABS_VOICE_ID가 설정되지 않았습니다.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = ElevenLabs(api_key=settings.elevenlabs_api_key)

    # ElevenLabs 음성 생성
    audio = client.generate(
        text=text,
        voice=settings.elevenlabs_voice_id,
        model="eleven_multilingual_v2",
        voice_settings=VoiceSettings(
            stability=settings.elevenlabs_stability,  # 0.35 (자연스러움)
            similarity_boost=0.75,
        ),
    )

    # MP3로 저장
    with open(output_path, "wb") as f:
        f.write(audio)

    # 음성 길이 추정
    estimated_duration = len(text) / 5.5

    return max(estimated_duration, 1.0)


async def synthesize_timeline(timeline: list, output_dir: Path) -> tuple[Path, list]:
    """타임라인의 모든 세그먼트를 음성으로 합성하고 연결한다.

    Args:
        timeline: [{"text": "...", "start": 0.0, "duration": 5.0}, ...]
        output_dir: 출력 디렉토리

    Returns:
        (최종 MP3 경로, 타이밍이 업데이트된 timeline)
    """
    settings = get_settings()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 환경에 맞게 TTS 함수 선택
    if settings.environment == "production" and settings.elevenlabs_api_key:
        synthesize_func = synthesize_with_elevenlabs
        tts_name = "ElevenLabs"
    else:
        synthesize_func = synthesize_with_edge_tts
        tts_name = "edge-tts"

    print(f"📢 TTS 모드: {tts_name}")

    # 각 세그먼트를 음성으로 변환
    audio_segments = []
    updated_timeline = []
    current_start = 0.0

    for i, segment in enumerate(timeline):
        text = segment.get("text", "")
        if not text:
            continue

        segment_path = output_dir / f"segment_{i:03d}.mp3"

        # 음성 생성
        actual_duration = await synthesize_func(text, segment_path)

        audio_segments.append(segment_path)
        updated_timeline.append({
            "keyword": segment.get("keyword", ""),
            "text": text,
            "start": current_start,
            "duration": actual_duration,
            "audio_path": str(segment_path),
        })

        current_start += actual_duration

    # 모든 오디오 세그먼트를 MP3로 합치기
    final_audio_path = output_dir / "narration.mp3"

    if len(audio_segments) == 1:
        # 세그먼트가 하나면 복사만
        import shutil
        shutil.copy(audio_segments[0], final_audio_path)
    else:
        # 여러 세그먼트를 ffmpeg으로 합치기
        await concatenate_audio_segments(audio_segments, final_audio_path)

    return final_audio_path, updated_timeline


async def concatenate_audio_segments(segments: list[Path], output_path: Path) -> None:
    """여러 MP3 파일을 하나로 합친다 (ffmpeg 사용).

    Args:
        segments: MP3 파일 경로 리스트
        output_path: 출력 MP3 경로
    """
    import subprocess

    # ffmpeg concat demuxer 파일 생성
    concat_file = output_path.parent / "concat.txt"
    with open(concat_file, "w") as f:
        for seg in segments:
            f.write(f"file '{seg.absolute()}'\n")

    # ffmpeg로 합치기
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                "-y",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg 합성 실패: {result.stderr}")

    finally:
        # 임시 파일 정리
        if concat_file.exists():
            concat_file.unlink()
