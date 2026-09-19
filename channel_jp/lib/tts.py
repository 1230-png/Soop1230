"""문장 하나를 넣으면 캐시된 mp3 하나가 나온다. 엔진은 둘 중 하나다.

- `elevenlabs` — 유료, API 키가 필요하다. 이 채널의 기본값이다.
- `edge` — 무료, 키가 없다. 되돌아갈 자리로 쓰지 **않는다**(아래 참고).

**엔진을 조용히 바꾸지 않는다.** 키가 없으면 멈춘다. 되돌아가게 해 두면
어느 날 아침 키가 만료됐을 때 목소리가 통째로 다른 영상이 채널에 올라가고,
아무도 모른다. 채널 자격 증명에 대체 경로를 두지 않는 것과 같은 이유다
(CLAUDE.md).

**느린 읽기는 두 번째 호출이 아니라 ffmpeg 로 만든다.** ElevenLabs 는 글자
수로 돈을 받는데, 같은 문장을 속도만 바꿔 두 번 보내면 값이 그대로 두 배가
된다. 대신 보통 속도 음성을 받아 `atempo` 로 늦춘다 — 음높이는 그대로고
글자 값은 한 번만 든다. 수면 팩 한 편 기준으로 대략 4,400자가 3,300자로
내려간다.

`--offline` 은 합성 대신 글자 수에 맞춘 무음을 넣는다. 네트워크 없이
파이프라인 전체(타이밍·카드·이어붙이기·인코딩)를 검증할 수 있고, 돈도 러너
시간도 태우지 않고 빌드를 디버깅하는 유일한 방법이다.
"""

import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "tts_cache"

# --offline 에서만 쓰는 대략의 말 속도. 무음 길이를 그럴듯하게 만들어 타이밍과
# 챕터 표시가 믿을 만한 범위에 머물게 하려는 값이다.
#
# 영어판은 14.0 을 쓴다. 여기서 절반으로 낮춘 이유는 일본어가 글자당 소리가
# 길기 때문이다 — 가나 한 글자가 대체로 한 박이라, 같은 글자 수라도 영어보다
# 오래 걸린다. 14 로 두면 --offline 빌드가 실제 길이의 절반으로 나와서
# target_minutes 검사가 통째로 거짓말을 한다.
OFFLINE_CHARS_PER_SECOND = 7.0
OFFLINE_MIN_SECONDS = 0.8

ELEVEN_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"
ELEVEN_KEY_ENV = "ELEVENLABS_API_KEY"
# 다국어 모델이라야 일본어와 한국어를 한 목소리로 읽는다.
ELEVEN_MODEL = "eleven_multilingual_v2"
ELEVEN_TIMEOUT = 120

# atempo 가 받는 범위. 밖으로 나가면 ffmpeg 이 조용히 이상한 것을 낸다.
TEMPO_MIN, TEMPO_MAX = 0.5, 2.0

RATE_PATTERN = re.compile(r"^([+-]?\d+)%$")


class TTSError(RuntimeError):
    pass


def _key(text: str, voice: str, rate: str, engine: str) -> str:
    return hashlib.sha1(
        f"{engine}|{text}|{voice}|{rate}".encode("utf-8")).hexdigest()


def tempo_for(rate: str) -> float:
    """`-20%` 를 atempo 값 0.8 로.

    edge-tts 는 이 문자열을 그대로 받지만 ElevenLabs 에는 속도 손잡이가 없다.
    그래서 같은 표기를 읽어 ffmpeg 쪽으로 넘긴다 — packs.yaml 이 엔진마다
    다른 말을 하지 않게 하려는 것이다.
    """
    found = RATE_PATTERN.match(rate.strip())
    if not found:
        raise TTSError(f"속도 표기를 읽을 수 없다: {rate!r} (예: '-20%')")
    tempo = 1.0 + int(found.group(1)) / 100
    if not TEMPO_MIN <= tempo <= TEMPO_MAX:
        raise TTSError(
            f"속도 {rate} 는 atempo 범위({TEMPO_MIN}~{TEMPO_MAX}) 밖이다")
    return tempo


def build_edge_command(text: str, voice: str, rate: str, out_path: Path) -> list:
    """edge-tts argv.

    `--rate=-15%` 는 한 토큰이어야 한다. 둘로 나눠 넘기면(`--rate`, `-15%`)
    argparse 가 앞의 대시를 다른 옵션의 시작으로 읽고 한마디도 말하기 전에
    상태 2 로 끝난다. 대시로 시작하는 본문도 같은 위험이라, 둘 다 '=' 로 붙인다.
    """
    return [
        "edge-tts",
        f"--voice={voice}",
        f"--rate={rate}",
        f"--text={text}",
        f"--write-media={out_path}",
    ]


def build_eleven_request(text: str, voice: str, api_key: str):
    """ElevenLabs 요청 하나.

    본문과 헤더를 따로 만들어 두는 이유는 테스트가 네트워크 없이 여기까지를
    확인할 수 있게 하려는 것이다. 키는 헤더에만 들어가고 로그에 남지 않는다.
    """
    body = json.dumps({
        "text": text,
        "model_id": ELEVEN_MODEL,
        "voice_settings": {
            # 수면·학습용이라 표현을 크게 흔들지 않는다. 같은 문장을 다시
            # 합성해도 비슷하게 나와야 한 영상 안에서 톤이 튀지 않는다.
            "stability": 0.6,
            "similarity_boost": 0.8,
            "style": 0.0,
        },
    }).encode("utf-8")
    request = urllib.request.Request(
        ELEVEN_URL.format(voice=voice), data=body, method="POST")
    request.add_header("xi-api-key", api_key)
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "audio/mpeg")
    return request


def api_key(env=None) -> str:
    env = os.environ if env is None else env
    value = (env.get(ELEVEN_KEY_ENV) or "").strip()
    if not value:
        raise TTSError(
            f"{ELEVEN_KEY_ENV} 가 없다. 다른 엔진으로 돌아가지 않는다 — "
            "목소리가 바뀐 채로 발행되는 것이 멈추는 것보다 나쁘다.")
    return value


def duration_of(path: Path) -> float:
    """오디오 길이(초). ffprobe 로 잰다."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True)
    return float(out.stdout.strip())


def make_silence(seconds: float, out_path: Path) -> Path:
    """그 길이의 무음 mp3."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", f"{seconds:.3f}", "-q:a", "9", str(out_path)],
        check=True, capture_output=True)
    return out_path


def stretch(source: Path, tempo: float, out_path: Path) -> Path:
    """음높이를 그대로 두고 속도만 바꾼다."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(source), "-filter:a", f"atempo={tempo:.3f}",
         "-q:a", "4", str(out_path)],
        check=True, capture_output=True)
    return out_path


def _fetch_eleven(text: str, voice: str, path: Path, env=None) -> None:
    """ElevenLabs 에서 mp3 를 받아 `path` 에 쓴다."""
    request = build_eleven_request(text, voice, api_key(env))
    try:
        with urllib.request.urlopen(request, timeout=ELEVEN_TIMEOUT) as response:
            audio = response.read()
    except urllib.error.HTTPError as error:
        # 본문에 사유가 들어 있다(글자 한도 초과·잘못된 voice_id 등). 키는
        # 헤더에만 있으므로 여기 실려 나오지 않는다.
        detail = error.read()[:300].decode("utf-8", "replace")
        raise TTSError(f"ElevenLabs HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise TTSError(f"ElevenLabs 에 닿지 못했다: {error.reason}") from error

    if not audio:
        raise TTSError("ElevenLabs 가 빈 응답을 줬다")
    path.write_bytes(audio)


def synthesize(text: str, voice: str, rate: str = "+0%", *,
               offline: bool = False, attempts: int = 3,
               engine: str = "elevenlabs", env=None) -> Path:
    """`voice` 가 읽은 `text` 의 mp3 경로.

    결과는 캐시된다. 같은 인자로 두 번 부르면 ffprobe 한 번 값밖에 안 든다 —
    글자마다 돈이 나가는 엔진에서는 이것이 비용 장치이기도 하다.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_key(text, voice, rate, engine)}.mp3"
    if path.exists() and path.stat().st_size > 0:
        return path

    if offline:
        seconds = max(OFFLINE_MIN_SECONDS, len(text) / OFFLINE_CHARS_PER_SECOND)
        return make_silence(seconds, path)

    if engine == "elevenlabs":
        return _synthesize_eleven(text, voice, rate, path, attempts, env)
    if engine == "edge":
        return _synthesize_edge(text, voice, rate, path, attempts)
    raise TTSError(f"모르는 엔진: {engine!r}")


def _synthesize_eleven(text: str, voice: str, rate: str, path: Path,
                       attempts: int, env) -> Path:
    """느린 읽기는 보통 속도를 받아 늦춘다 — 글자 값을 두 번 내지 않으려고."""
    tempo = tempo_for(rate)
    if tempo != 1.0:
        normal = synthesize(text, voice, "+0%", attempts=attempts,
                            engine="elevenlabs", env=env)
        return stretch(normal, tempo, path)

    last = None
    for attempt in range(1, attempts + 1):
        try:
            _fetch_eleven(text, voice, path, env)
            if path.exists() and path.stat().st_size > 0:
                return path
            last = TTSError("빈 파일이 만들어졌다")
        except TTSError as error:
            last = error
        # 실패한 시도가 잘린 파일을 남길 수 있다. 다음번에 그것이 캐시로
        # 잡히면 조용히 틀린 소리가 나가므로, 재시도 전에 지운다.
        path.unlink(missing_ok=True)
        if attempt < attempts:
            time.sleep(2 * attempt)

    raise TTSError(f"ElevenLabs 가 {attempts}번 모두 실패했다 ({text!r}): {last}")


def _synthesize_edge(text: str, voice: str, rate: str, path: Path,
                     attempts: int) -> Path:
    last = None
    for attempt in range(1, attempts + 1):
        try:
            subprocess.run(build_edge_command(text, voice, rate, path),
                           check=True, capture_output=True)
            if path.exists() and path.stat().st_size > 0:
                return path
            last = TTSError("edge-tts 가 빈 파일을 썼다")
        except subprocess.CalledProcessError as error:
            last = error
        path.unlink(missing_ok=True)
        if attempt < attempts:
            time.sleep(2 * attempt)

    raise TTSError(f"edge-tts 가 {attempts}번 모두 실패했다 ({text!r}): {last}")
