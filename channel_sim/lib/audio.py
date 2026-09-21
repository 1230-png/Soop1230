"""소리를 계산해서 만든다. 음원도, 음성도 쓰지 않는다.

무음으로 두면 사람들이 십 초 안에 끈다. 그렇다고 배경음악을 깔면 저작권을
관리해야 하고, 내레이션을 넣으면 이 채널이 피하려는 바로 그 자동 음성이 된다.

그래서 **지금 만지고 있는 값 자체를 소리로 바꾼다.** 작은 값은 낮게, 큰 값은
높게. 그러면 소리가 배경이 아니라 화면의 일부가 된다 — 정렬이 끝나갈수록
음이 정리되는 것이 들리고, 그게 진행 상황을 귀로 알려 준다.

음을 반음 단위로 그대로 매핑하면 사이렌처럼 들린다. 5음 음계 위에 올려
놓으면 같은 정보가 음악처럼 들린다. 20분을 견디게 만드는 것이 이 한 줄이다.
"""

from __future__ import annotations

import numpy as np

RATE = 44100

# 단5음 음계. 어느 두 음을 겹쳐 울려도 불협이 되지 않아, 값이 마구 튀는
# 구간에서도 듣기 싫어지지 않는다.
SCALE = [0, 3, 5, 7, 10]
OCTAVES = 4
BASE_HZ = 196.0     # G3


def scale_table() -> np.ndarray:
    """5음 음계를 4옥타브로 펼친 주파수 표."""
    steps = [o * 12 + s for o in range(OCTAVES) for s in SCALE]
    return BASE_HZ * (2.0 ** (np.array(steps, dtype=np.float64) / 12.0))


class ToneWriter:
    """프레임마다 한 알씩 소리를 이어 붙인다.

    위상을 이어 간다. 알마다 사인파를 0에서 새로 시작하면 경계마다 파형이
    끊겨 '틱' 소리가 난다 — 36,000번이면 그것만으로 못 듣는 소리가 된다.
    """

    # 0.28 로 만들었더니 피크가 17% 에 그쳤다. 유튜브의 음량 정규화는 시끄러운
    # 것을 낮추기만 하고 조용한 것을 올려 주지 않아서, 그대로 두면 다른 영상
    # 보다 눈에 띄게 작게 들린다. 0.40 이면 피크가 34% 언저리다.
    def __init__(self, path, fps: int, gain: float = 0.40) -> None:
        self.handle = open(path, "wb")
        self.samples = int(round(RATE / fps))
        self.table = scale_table()
        self.phase = 0.0
        self.gain = gain
        # 앞 알의 진폭. 여기서부터 이어야 음량이 갑자기 튀지 않는다.
        self.level = 0.0

    def push(self, value: float | None, loud: float = 1.0) -> None:
        """값 하나를 한 프레임 길이의 소리로.

        `value` 가 None 이면 그 프레임은 쉰다 — 끝난 뒤 정지 화면이 이어지는
        구간에서 소리만 계속 나면 이상하다.
        """
        n = self.samples
        if value is None:
            target = 0.0
            freq = self.table[0]
        else:
            index = int(np.clip(value, 0.0, 1.0) * (len(self.table) - 1))
            freq = float(self.table[index])
            target = float(np.clip(loud, 0.0, 1.0))

        step = 2 * np.pi * freq / RATE
        phases = self.phase + step * np.arange(n, dtype=np.float64)
        self.phase = float((phases[-1] + step) % (2 * np.pi))

        # 앞 알의 음량에서 이번 음량으로 매끄럽게 건너간다.
        envelope = np.linspace(self.level, target, n)
        self.level = target

        wave = np.sin(phases)
        # 사인만 쓰면 너무 맑아 묻힌다. 3배음을 조금 섞으면 작은 스피커에서도
        # 음이 구분된다.
        wave = 0.82 * wave + 0.18 * np.sin(3 * phases)

        block = (wave * envelope * self.gain * 32767.0)
        self.handle.write(np.clip(block, -32768, 32767).astype("<i2").tobytes())

    def close(self) -> None:
        self.handle.close()
