"""정렬 알고리즘을 **사건의 열**로 내놓는다.

보통은 정렬 함수가 정렬된 배열을 돌려주면 끝이지만, 여기서 필요한 것은
결과가 아니라 과정이다. 그래서 전부 제너레이터로 쓰고, 한 번의 비교와 한
번의 쓰기마다 사건을 하나씩 내보낸다. 화면과 소리는 그 사건을 받아 그린다.

사건은 `("compare", i, j)` 또는 `("write", i, j)` 두 가지다. 이 둘만 있으면
어떤 알고리즘이든 같은 방식으로 그릴 수 있고, **비교 횟수와 쓰기 횟수를
공짜로 세게 된다** — 영상 끝의 순위표가 그 숫자다.

배열은 제자리에서 고친다. 호출하는 쪽이 같은 리스트를 들고 있으므로,
사건을 하나 받을 때마다 그 시점의 배열 상태를 그대로 볼 수 있다.
"""

from __future__ import annotations


def bubble(a: list[int]):
    """버블 정렬. 한 바퀴에 한 칸씩만 제자리를 찾는다.

    한 바퀴를 돌았는데 교환이 한 번도 없으면 끝난 것이다. 이 검사를 빼면
    이미 정렬된 입력에도 n바퀴를 다 돈다 — 화면에서 아무 일도 안 일어나는
    구간이 길게 남는다.
    """
    n = len(a)
    for i in range(n):
        swapped = False
        for j in range(n - 1 - i):
            yield ("compare", j, j + 1)
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                yield ("write", j, j + 1)
                swapped = True
        if not swapped:
            return


def cocktail(a: list[int]):
    """칵테일 정렬. 버블을 좌우로 번갈아 민다.

    화면에서 버블과 나란히 두면 차이가 한눈에 보인다 — 버블은 큰 값만
    오른쪽으로 밀지만 이쪽은 작은 값도 같이 왼쪽으로 끌어온다.
    """
    lo, hi = 0, len(a) - 1
    while lo < hi:
        swapped = False
        for j in range(lo, hi):
            yield ("compare", j, j + 1)
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                yield ("write", j, j + 1)
                swapped = True
        hi -= 1
        for j in range(hi, lo, -1):
            yield ("compare", j - 1, j)
            if a[j - 1] > a[j]:
                a[j - 1], a[j] = a[j], a[j - 1]
                yield ("write", j - 1, j)
                swapped = True
        lo += 1
        if not swapped:
            return


def insertion(a: list[int]):
    """삽입 정렬. 왼쪽이 항상 정렬된 상태로 유지된다."""
    for i in range(1, len(a)):
        key = a[i]
        j = i - 1
        while j >= 0:
            yield ("compare", j, i)
            if a[j] <= key:
                break
            a[j + 1] = a[j]
            yield ("write", j + 1, j)
            j -= 1
        a[j + 1] = key
        yield ("write", j + 1, j + 1)


def selection(a: list[int]):
    """선택 정렬. 비교는 많고 쓰기는 가장 적다.

    이 대비가 영상 끝 순위표의 핵심이다 — 비교로 줄을 세우면 꼴찌권인데
    쓰기로 줄을 세우면 1등이다. 「빠르다」가 한 가지 뜻이 아니라는 것을
    말로 설명하지 않고 숫자로 보여 줄 수 있다.
    """
    n = len(a)
    for i in range(n):
        lo = i
        for j in range(i + 1, n):
            yield ("compare", lo, j)
            if a[j] < a[lo]:
                lo = j
        if lo != i:
            a[i], a[lo] = a[lo], a[i]
            yield ("write", i, lo)


def gnome(a: list[int]):
    """놈 정렬. 한 칸 보고 아니면 한 칸 물러선다."""
    i = 0
    n = len(a)
    while i < n:
        if i == 0:
            i += 1
            continue
        yield ("compare", i - 1, i)
        if a[i - 1] <= a[i]:
            i += 1
        else:
            a[i - 1], a[i] = a[i], a[i - 1]
            yield ("write", i - 1, i)
            i -= 1


def comb(a: list[int]):
    """빗질 정렬. 버블인데 간격을 두고 비교한다.

    간격을 1.3으로 줄여 나가는 것이 원논문 값이다. 마지막에 간격이 1이
    되면 버블과 같아지지만, 그때는 거의 정렬돼 있어 금방 끝난다.
    """
    n = len(a)
    gap = n
    swapped = True
    while gap > 1 or swapped:
        gap = max(1, int(gap / 1.3))
        swapped = False
        for i in range(n - gap):
            yield ("compare", i, i + gap)
            if a[i] > a[i + gap]:
                a[i], a[i + gap] = a[i + gap], a[i]
                yield ("write", i, i + gap)
                swapped = True


def shell(a: list[int]):
    """셸 정렬. 삽입 정렬을 간격을 두고 여러 번 돌린다."""
    n = len(a)
    gap = n // 2
    while gap > 0:
        for i in range(gap, n):
            key = a[i]
            j = i
            while j >= gap:
                yield ("compare", j - gap, i)
                if a[j - gap] <= key:
                    break
                a[j] = a[j - gap]
                yield ("write", j, j - gap)
                j -= gap
            a[j] = key
            yield ("write", j, j)
        gap //= 2


def heap(a: list[int]):
    """힙 정렬. 배열을 트리로 보고 가장 큰 값을 뒤로 뺀다."""

    def sift(lo: int, hi: int):
        root = lo
        while root * 2 + 1 < hi:
            child = root * 2 + 1
            if child + 1 < hi:
                yield ("compare", child, child + 1)
                if a[child] < a[child + 1]:
                    child += 1
            yield ("compare", root, child)
            if a[root] >= a[child]:
                return
            a[root], a[child] = a[child], a[root]
            yield ("write", root, child)
            root = child

    n = len(a)
    for start in range(n // 2 - 1, -1, -1):
        yield from sift(start, n)
    for end in range(n - 1, 0, -1):
        a[0], a[end] = a[end], a[0]
        yield ("write", 0, end)
        yield from sift(0, end)


def merge(a: list[int]):
    """병합 정렬. 제자리가 아니라 보조 배열을 쓴다.

    보조 배열로 쓰는 것은 화면에 안 보이지만, 되쓰는 순간은 보인다 —
    그래서 쓰기 사건은 되쓸 때만 내보낸다. 실제 쓰기 횟수와 맞는다.
    """

    def run(lo: int, hi: int):
        if hi - lo <= 1:
            return
        mid = (lo + hi) // 2
        yield from run(lo, mid)
        yield from run(mid, hi)
        left, right = a[lo:mid], a[mid:hi]
        i = j = 0
        for k in range(lo, hi):
            if i < len(left) and j < len(right):
                yield ("compare", lo + i, mid + j)
                take_left = left[i] <= right[j]
            else:
                take_left = i < len(left)
            if take_left:
                a[k] = left[i]
                i += 1
            else:
                a[k] = right[j]
                j += 1
            yield ("write", k, k)

    yield from run(0, len(a))


def quick(a: list[int]):
    """퀵 정렬. 가운데 값을 축으로 삼는다(Lomuto).

    축을 맨 끝 값으로 잡는 교과서 판은 **이미 정렬된 입력에서 O(n²)로
    떨어진다.** 가운데를 골라 끝과 바꿔 두면 그 최악이 사라지고, 영상에서도
    한 알고리즘만 혼자 몇 배로 늘어지는 일이 없다.
    """

    def run(lo: int, hi: int):
        if lo >= hi:
            return
        mid = (lo + hi) // 2
        if mid != hi:
            a[mid], a[hi] = a[hi], a[mid]
            yield ("write", mid, hi)
        pivot = a[hi]
        i = lo
        for j in range(lo, hi):
            yield ("compare", j, hi)
            if a[j] < pivot:
                if i != j:
                    a[i], a[j] = a[j], a[i]
                    yield ("write", i, j)
                i += 1
        a[i], a[hi] = a[hi], a[i]
        yield ("write", i, hi)
        yield from run(lo, i - 1)
        yield from run(i + 1, hi)

    yield from run(0, len(a) - 1)


def radix_lsd(a: list[int]):
    """기수 정렬. 값을 비교하지 않고 자릿수로 나눠 담는다.

    **비교 사건이 하나도 없는 유일한 알고리즘이다.** 순위표에서 비교 횟수가
    0으로 찍히는데, 그게 오류가 아니라 이 알고리즘의 정체다 — 비교 기반
    정렬의 하한인 n log n 을 왜 이쪽은 안 따르는지가 거기서 보인다.
    """
    n = len(a)
    if n == 0:
        return
    exp = 1
    highest = max(a)
    while highest // exp > 0:
        buckets = [[] for _ in range(10)]
        for i in range(n):
            buckets[(a[i] // exp) % 10].append(a[i])
        k = 0
        for bucket in buckets:
            for value in bucket:
                a[k] = value
                yield ("write", k, k)
                k += 1
        exp *= 10


def tim_lite(a: list[int]):
    """팀소트의 뼈대. 짧은 구간은 삽입 정렬, 그 뒤 병합.

    실제 CPython 의 팀소트는 여기에 갤로핑과 런 탐지가 더 붙는다. 그것까지
    넣으면 화면에서 무슨 일이 일어나는지 알아볼 수 없어 뼈대만 남겼다.
    **실무 정렬이 왜 퀵소트가 아닌지**는 이 뼈대만으로도 보인다 — 이미
    정렬된 구간을 만나면 거의 아무 일도 하지 않는다.
    """
    n = len(a)
    run = 32

    for start in range(0, n, run):
        stop = min(start + run, n)
        for i in range(start + 1, stop):
            key = a[i]
            j = i - 1
            while j >= start:
                yield ("compare", j, i)
                if a[j] <= key:
                    break
                a[j + 1] = a[j]
                yield ("write", j + 1, j)
                j -= 1
            a[j + 1] = key
            yield ("write", j + 1, j + 1)

    size = run
    while size < n:
        for lo in range(0, n, size * 2):
            mid, hi = min(lo + size, n), min(lo + size * 2, n)
            if mid >= hi:
                continue
            left, right = a[lo:mid], a[mid:hi]
            i = j = 0
            for k in range(lo, hi):
                if i < len(left) and j < len(right):
                    yield ("compare", lo + i, mid + j)
                    take_left = left[i] <= right[j]
                else:
                    take_left = i < len(left)
                if take_left:
                    a[k] = left[i]
                    i += 1
                else:
                    a[k] = right[j]
                    j += 1
                yield ("write", k, k)
        size *= 2


# 화면에 나갈 순서. 느리고 눈에 잘 보이는 것부터 두어, 뒤로 갈수록
# "어떻게 저게 되지" 하는 쪽이 오게 했다. 마지막 기수 정렬은 비교를 아예
# 하지 않아 앞의 열한 개와 성질이 다르다 — 그래서 끝에 둔다.
ALGORITHMS = [
    ("bubble", "버블 정렬", "옆 칸과 비교해 한 칸씩 민다", bubble),
    ("cocktail", "칵테일 정렬", "버블을 좌우로 번갈아", cocktail),
    ("gnome", "놈 정렬", "틀리면 한 칸 물러선다", gnome),
    ("insertion", "삽입 정렬", "왼쪽은 늘 정렬돼 있다", insertion),
    ("selection", "선택 정렬", "비교는 최다, 쓰기는 최소", selection),
    ("shell", "셸 정렬", "간격을 둔 삽입 정렬", shell),
    ("comb", "빗질 정렬", "간격을 둔 버블 정렬", comb),
    ("merge", "병합 정렬", "쪼개고 합친다", merge),
    ("quick", "퀵 정렬", "축을 기준으로 가른다", quick),
    ("heap", "힙 정렬", "배열을 트리로 본다", heap),
    ("tim_lite", "팀소트 (뼈대)", "실무가 실제로 쓰는 것", tim_lite),
    ("radix_lsd", "기수 정렬", "비교를 하지 않는다", radix_lsd),
]


def collect(func, values: list[int], cap: int = 4_000_000) -> tuple[list, list[int]]:
    """사건을 전부 모으고, 배열의 최종 상태를 함께 돌려준다.

    한 번에 다 모으는 이유는 **총 사건 수를 미리 알아야 하기 때문이다.**
    한 꼭지를 정해진 시간 안에 끝내려면 프레임당 몇 사건을 소화할지
    정해야 하고, 그 값은 총량을 모르면 구할 수 없다.

    `cap` 은 안전장치다. 버그로 끝나지 않는 제너레이터를 만나면 메모리를
    다 쓰고 죽는 대신 여기서 멈춘다.
    """
    work = list(values)
    events = []
    for event in func(work):
        events.append(event)
        if len(events) >= cap:
            raise RuntimeError(f"사건이 {cap}개를 넘었다 — 끝나지 않는 정렬인가")
    return events, work
