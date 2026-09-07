"""나레이션 음성. edge-tts 를 쓰고, 키도 요금도 없다."""

import asyncio
import subprocess
from pathlib import Path

# 담백한 남성 한국어 음성. 공포·탐욕을 자극하지 않는 채널 톤에 맞춘다.
DEFAULT_VOICE = "ko-KR-InJoonNeural"


def edge_tts_speak(text, out_path, voice=DEFAULT_VOICE):
    """edge-tts 로 한 장면을 읽어 mp3 로 저장한다."""
    import edge_tts

    async def run():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(out_path))

    asyncio.run(run())
    return out_path


def silent_speak(text, out_path, voice=DEFAULT_VOICE):
    """말하지 않고 길이만 맞춘 무음을 만든다.

    네트워크가 막힌 곳에서 영상 조립을 끝까지 검증하려고 둔다.
    한국어를 초당 약 5.5글자로 읽는다고 보고 길이를 잡는다.
    """
    seconds = max(1.5, len(text) / 5.5)
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", f"{seconds:.2f}", "-q:a", "9", str(out_path)],
        check=True, capture_output=True,
    )
    return out_path


def narrate(scenes, outdir, speak=edge_tts_speak, voice=DEFAULT_VOICE):
    """장면마다 음성 파일을 만들어 경로 목록을 돌려준다."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, scene in enumerate(scenes, start=1):
        path = outdir / f"line_{index:03d}.mp3"
        speak(scene.narration, path, voice)
        paths.append(path)
    return paths
