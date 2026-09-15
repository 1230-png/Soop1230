"""나레이션 음성. edge-tts 를 먼저 쓰고, 막히면 일레븐랩스로 넘어간다.

edge-tts 는 키도 요금도 없어서 기본으로 둔다. 다만 **깃허브 러너처럼
데이터센터에서 나가는 요청은 마이크로소프트가 막는다** — NoAudioReceived 로
끝난다. 실제로 그렇게 막혔다. 그래서 무인 실행에서는 대안이 필요하다.

ELEVENLABS_API_KEY 가 있으면 그쪽으로 넘어간다. 없으면 왜 실패했는지 적고 멈춘다.
무음으로 대신 만들지 않는다 — 나레이션 없는 영상이 발행되면 그게 더 나쁘다.
"""

import asyncio
import os
import subprocess
import time
from pathlib import Path

# 담백한 남성 한국어 음성. 공포·탐욕을 자극하지 않는 채널 톤에 맞춘다.
DEFAULT_VOICE = "ko-KR-InJoonNeural"
EDGE_ATTEMPTS = 3
ELEVENLABS_KEY_ENV = "ELEVENLABS_API_KEY"
ELEVENLABS_DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"


class VoiceError(RuntimeError):
    """음성을 만들지 못했다."""


def _edge_once(text, out_path, voice):
    import edge_tts

    async def run():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(out_path))

    asyncio.run(run())
    return out_path


def edge_tts_speak(text, out_path, voice=DEFAULT_VOICE):
    """edge-tts 로 한 장면을 읽어 mp3 로 저장한다. 막히면 일레븐랩스로 넘어간다."""
    last = None
    for attempt in range(1, EDGE_ATTEMPTS + 1):
        try:
            return _edge_once(text, out_path, voice)
        except Exception as error:
            last = error
            if attempt < EDGE_ATTEMPTS:
                time.sleep(attempt * 2)

    if os.environ.get(ELEVENLABS_KEY_ENV):
        return elevenlabs_speak(text, out_path)

    raise VoiceError(
        f"edge-tts 가 {EDGE_ATTEMPTS}회 모두 실패했다: {type(last).__name__}: {last}\n"
        "  깃허브 러너 같은 데이터센터 주소는 마이크로소프트가 막는다.\n"
        f"  {ELEVENLABS_KEY_ENV} 를 넣으면 그쪽으로 넘어간다."
    ) from last


def elevenlabs_speak(text, out_path, voice=None):
    """일레븐랩스로 읽는다. 데이터센터에서도 막히지 않는다."""
    import requests

    voice_id = voice or os.environ.get("ELEVENLABS_VOICE_ID", ELEVENLABS_DEFAULT_VOICE_ID)
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": os.environ[ELEVENLABS_KEY_ENV],
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": text,
            "model_id": ELEVENLABS_MODEL_ID,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=60,
    )
    if response.status_code != 200:
        raise VoiceError(
            f"일레븐랩스가 {response.status_code} 를 돌려줬다: {response.text[:300]}"
        )
    Path(out_path).write_bytes(response.content)
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
