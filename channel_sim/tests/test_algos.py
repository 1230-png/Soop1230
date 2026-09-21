"""정렬이 정말 정렬하는지. 네트워크도 외부 API도 타지 않는다.

이 검사가 없으면 무엇이 깨지는가: 영상은 끝까지 만들어지고 업로드도 되는데
화면의 막대만 정렬이 덜 된 채로 끝난다. **발행 뒤에야 보인다.** 실제로
삽입 정렬이 그렇게 한 번 새 나갔다 — 사건을 마지막 하나 덜 소화하는 바람에
제너레이터 안의 마지막 대입이 실행되지 않았다.
"""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import algos  # noqa: E402

CASES = [(key, func) for key, _, _, func in algos.ALGORITHMS]


def shuffled(n: int, seed: int) -> list[int]:
    return random.Random(seed).sample(range(1, n + 1), n)


@pytest.mark.parametrize("key,func", CASES)
def test_정렬된다(key, func):
    values = shuffled(120, 3)
    _, out = algos.collect(func, values)
    assert out == sorted(values), f"{key} 가 정렬하지 못했다"


@pytest.mark.parametrize("key,func", CASES)
@pytest.mark.parametrize("values", [
    [],                     # 빈 배열
    [1],                    # 한 개
    [2, 1],                 # 두 개
    list(range(1, 41)),     # 이미 정렬됨
    list(range(40, 0, -1)),  # 거꾸로
    [7] * 20,               # 전부 같은 값
])
def test_구석진_입력(key, func, values):
    """이미 정렬된 입력과 역순 입력이 최악을 만드는 자리다.

    퀵 정렬은 축을 맨 끝으로 잡으면 정렬된 입력에서 재귀가 n 단계로 깊어져
    RecursionError 가 난다. 가운데를 축으로 바꾼 것이 그 때문이고, 이 검사가
    그 선택을 잡아 준다.
    """
    _, out = algos.collect(func, values)
    assert out == sorted(values), f"{key}: {values[:6]}"


def test_기수정렬은_비교하지_않는다():
    """비교 0 은 오류가 아니라 이 알고리즘의 정체다.

    순위표에서 1등으로 찍히는데, 그 0 이 버그로 보여 누가 '고치면' 영상이
    말하려는 것이 사라진다 — 비교 기반 정렬의 하한을 왜 이쪽만 안 따르는지가
    그 0 이다.
    """
    events, _ = algos.collect(algos.radix_lsd, shuffled(80, 5))
    assert [e for e in events if e[0] == "compare"] == []


def test_선택정렬은_쓰기가_가장_적다():
    """비교로 줄을 세우면 꼴찌권인데 쓰기로 세우면 1등이다.

    이 어긋남이 영상의 결론이라, 숫자가 뒤집히면 결론이 틀린 것이 된다.
    """
    values = shuffled(120, 7)
    writes = {}
    for key, _, _, func in algos.ALGORITHMS:
        events, _ = algos.collect(func, values)
        writes[key] = sum(1 for e in events if e[0] == "write")
    assert min(writes, key=writes.get) == "selection"


def test_사건은_두_종류뿐():
    """화면과 소리가 이 둘만 알고 있다. 새 종류가 생기면 조용히 무시된다."""
    events, _ = algos.collect(algos.quick, shuffled(60, 11))
    assert {e[0] for e in events} <= {"compare", "write"}


def test_상한을_넘으면_멈춘다():
    """끝나지 않는 제너레이터를 만나도 메모리를 다 쓰기 전에 죽는다."""

    def 영원히(a):
        while True:
            yield ("compare", 0, 0)

    with pytest.raises(RuntimeError):
        algos.collect(영원히, [3, 1, 2], cap=500)
