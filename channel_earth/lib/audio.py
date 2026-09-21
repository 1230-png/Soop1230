"""소리도 데이터에서 만든다. 음원도, 음성도 쓰지 않는다.

지진 하나가 소리 하나다. **높이는 깊이가, 크기는 규모가 정한다.**

- 얕을수록 높고 맑게. 같은 규모라도 얕은 지진이 지표에 훨씬 크게 온다
- 깊을수록 낮고 둔하게. 깊은 곳에서 온 것은 실제로도 둔하게 느껴진다

그래서 눈을 떼도 무슨 일이 일어나는지 들린다. 잔잔하다가 낮고 큰 소리가
한 번 나면 깊고 큰 지진이 있었다는 뜻이고, 그게 자막보다 빠르다.

크기는 규모를 그대로 쓰지 않는다. 규모는 로그 눈금이라 4와 7의 에너지 차이가
3만 배인데, 그대로 진폭에 넣으면 규모 4 이하는 아예 안 들린다. 들리되
차이는 남게 눌러서 쓴다.
"""

from __future__ import annotations

import numpy as np

RATE = 44100

# 단5음 음계. 어느 둘이 겹쳐 울려도 불협이 되지 않는다. 지진은 몰려서
# 일어나므로(여진) 동시에 서너 개가 울리는 일이 잦다.
SCALE = [0, 3, 5, 7, 10]
OCTAVES = 5
BASE_HZ = 65.41    # C2


def scale_table() -> np.ndarray:
    steps = [o * 12 + s for o in range(OCTAVES) for s in SCALE]
    return BASE_HZ * (2.0 ** (np.array(steps, dtype=np.float64) / 12.0))


def pitch_for_depth(depth_km: float) -> float:
    """깊을수록 낮게. 0km 가 제일 높은 음, 700km 가 제일 낮은 음.

    깊이는 얕은 쪽에 몰려 있어서(대부분 35km 이내) 선형으로 나누면 거의
    모든 지진이 같은 음이 된다. 제곱근으로 펴면 얕은 구간이 넓게 퍼진다.
    """
    table = scale_table()
    t = np.clip(np.sqrt(max(0.0, depth_km) / 700.0), 0.0, 1.0)
    index = int(round((1.0 - t) * (len(table) - 1)))
    return float(table[index])


def level_for_magnitude(mag: float) -> float:
    """규모를 진폭으로. 로그를 한 번 더 눌러서 쓴다.

    규모 4를 기준으로 1 오를 때마다 약 1.7배. 실제 에너지 비는 32배지만
    그대로 쓰면 규모 2는 안 들리고 규모 7은 찢어진다.
    """
    return float(np.clip(0.11 * 10.0 ** (0.22 * (mag - 4.0)), 0.015, 0.95))


def strike(buffer: np.ndarray, at_second: float, freq: float, level: float,
           decay: float) -> None:
    """친 소리 하나를 버퍼에 더한다. 종이나 말렛처럼 붙었다 사그라든다.

    **더한다.** 겹치는 지진이 서로를 덮지 않고 같이 울려야, 여진이 몰린
    구간이 실제로 북적이게 들린다.
    """
    start = int(at_second * RATE)
    if start >= len(buffer):
        return
    length = min(int(decay * 4 * RATE), len(buffer) - start)
    if length <= 0:
        return

    t = np.arange(length, dtype=np.float64) / RATE
    envelope = np.exp(-t / decay)
    # 때린 순간의 '틱'을 없애려고 앞 3ms 를 세워 올린다.
    attack = int(0.003 * RATE)
    if attack > 0:
        envelope[:attack] *= np.linspace(0.0, 1.0, attack)

    wave = (np.sin(2 * np.pi * freq * t)
            + 0.35 * np.sin(2 * np.pi * freq * 2 * t)
            # 살짝 어긋난 배음. 완전 정수배만 쌓으면 전자음처럼 들린다.
            + 0.18 * np.sin(2 * np.pi * freq * 3.02 * t))
    buffer[start:start + length] += wave * envelope * level


def drone(buffer: np.ndarray, level: float = 0.035) -> None:
    """바닥에 깔리는 저음.

    지진이 뜸한 구간에서 완전한 무음이 되면 소리가 고장 난 줄 안다.
    아주 작게 깔아 두면 그 구간이 '조용한 것'으로 들린다 — 빈 것이 아니라.
    """
    t = np.arange(len(buffer), dtype=np.float64) / RATE
    buffer += (np.sin(2 * np.pi * 55.0 * t) * 0.6
               + np.sin(2 * np.pi * 82.5 * t) * 0.4) * level


def to_pcm16(buffer: np.ndarray, peak: float = 0.85) -> bytes:
    """정규화해서 16비트로.

    피크를 맞춰 두는 이유: 유튜브의 음량 정규화는 시끄러운 것을 낮추기만
    하고 조용한 것을 올려 주지 않는다. 지진이 적은 날 영상이 유독 작게
    들리면 안 되므로, 날마다 같은 피크로 맞춘다.
    """
    top = float(np.max(np.abs(buffer))) if buffer.size else 0.0
    if top > 0:
        buffer = buffer / top * peak
    return np.clip(buffer * 32767.0, -32768, 32767).astype("<i2").tobytes()
