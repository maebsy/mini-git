"""정렬 알고리즘 직접 구현 (``sorted()`` / ``list.sort()`` 사용 금지 제약 대응).

모든 함수는 같은 시그니처를 가진다::

    algorithm(items, key=None, reverse=False) -> list   # 원본은 바꾸지 않고 새 리스트 반환

비교 기준은 ``key`` 함수로 바꾼다. 예) 날짜 기준 ``key=lambda c: (c.timestamp, c.seq)``,
작성자 기준 ``key=lambda c: c.author.casefold()``.

키는 원소마다 **한 번만** 계산해서 ``(key, item)`` 쌍으로 정렬한다(decorate-sort-undecorate).
비교할 때마다 key 함수를 다시 부르면 O(n log n) 번 호출되기 때문이다.

=================  ==========  ==========  =========  ===========  =========================
알고리즘             최선         평균         최악        추가 공간      안정 정렬
=================  ==========  ==========  =========  ===========  =========================
merge_sort (기본)   n log n     n log n     n log n    O(n)         ✅ (같은 키의 원래 순서 유지)
quick_sort          n log n     n log n     n²         O(log n)     ❌
heap_sort           n log n     n log n     n log n    O(1)         ❌
insertion_sort      n           n²          n²         O(1)         ✅ (거의 정렬된 입력에 강함)
=================  ==========  ==========  =========  ===========  =========================
"""

from typing import Any, Callable, Iterable, List, Optional, Tuple

KeyFunc = Optional[Callable[[Any], Any]]


def _decorate(items: Iterable[Any], key: KeyFunc) -> List[Tuple[Any, Any]]:
    if key is None:
        return [(item, item) for item in items]
    return [(key(item), item) for item in items]


def _make_less(reverse: bool) -> Callable[[Any, Any], bool]:
    """reverse 여부에 따라 '앞에 와야 하는가' 비교 함수를 만든다.

    reverse=True 일 때 단순히 결과를 뒤집으면 같은 키의 순서까지 뒤집혀 안정성이 깨진다.
    그래서 비교 방향만 바꾸고, 같은 키는 항상 '앞에 와야 하지 않음(False)'으로 둔다.
    """
    if reverse:
        return lambda a, b: b < a
    return lambda a, b: a < b


# --------------------------------------------------------------------- merge sort
def merge_sort(items: Iterable[Any], key: KeyFunc = None, reverse: bool = False) -> List[Any]:
    """병합 정렬 (안정). 반으로 나눠 각각 정렬한 뒤 두 정렬 리스트를 합친다.

    합칠 때 왼쪽과 오른쪽의 키가 같으면 **왼쪽을 먼저** 가져오므로 안정 정렬이 된다.
    재귀 대신 바텀업(크기 1, 2, 4 … 구간을 차례로 병합)으로 구현해 재귀 한도와 무관하다.
    """
    less = _make_less(reverse)
    src = _decorate(items, key)
    n = len(src)
    if n < 2:
        return [item for _, item in src]
    dst: List[Tuple[Any, Any]] = [None] * n  # type: ignore[list-item]
    width = 1
    while width < n:
        for lo in range(0, n, 2 * width):
            mid = min(lo + width, n)
            hi = min(lo + 2 * width, n)
            i, j, k = lo, mid, lo
            while i < mid and j < hi:
                if less(src[j][0], src[i][0]):  # 오른쪽이 '엄격히' 앞설 때만 오른쪽 선택 → 안정
                    dst[k] = src[j]
                    j += 1
                else:
                    dst[k] = src[i]
                    i += 1
                k += 1
            while i < mid:
                dst[k] = src[i]
                i += 1
                k += 1
            while j < hi:
                dst[k] = src[j]
                j += 1
                k += 1
        src, dst = dst, src
        width *= 2
    return [item for _, item in src]


# --------------------------------------------------------------------- quick sort
def quick_sort(items: Iterable[Any], key: KeyFunc = None, reverse: bool = False) -> List[Any]:
    """퀵 정렬 (불안정). 피벗을 기준으로 작은 / 같은 / 큰 구간으로 나눈다(3-way partition).

    * 피벗: 처음·중간·끝의 중앙값(median-of-three) → 이미 정렬된 입력에서 O(n²) 회피
    * 3-way 분할: 같은 키가 많아도(예: 작성자 몇 명) 구간이 줄어들지 않는 문제 방지
    * 작은 구간부터 처리하고 큰 구간은 반복문으로 → 스택 깊이 O(log n)
    """
    less = _make_less(reverse)
    arr = _decorate(items, key)

    def median_of_three(lo: int, hi: int) -> Any:
        mid = (lo + hi) // 2
        a, b, c = arr[lo][0], arr[mid][0], arr[hi][0]
        if less(a, b):
            if less(b, c):
                return b
            return c if less(a, c) else a
        if less(a, c):
            return a
        return c if less(b, c) else b

    def sort(lo: int, hi: int) -> None:
        while lo < hi:
            if hi - lo < 16:  # 작은 구간은 삽입 정렬이 더 빠르다
                for i in range(lo + 1, hi + 1):
                    cur = arr[i]
                    j = i - 1
                    while j >= lo and less(cur[0], arr[j][0]):
                        arr[j + 1] = arr[j]
                        j -= 1
                    arr[j + 1] = cur
                return
            pivot = median_of_three(lo, hi)
            lt, i, gt = lo, lo, hi  # [lo,lt) < pivot, [lt,i) == pivot, (gt,hi] > pivot
            while i <= gt:
                if less(arr[i][0], pivot):
                    arr[lt], arr[i] = arr[i], arr[lt]
                    lt += 1
                    i += 1
                elif less(pivot, arr[i][0]):
                    arr[i], arr[gt] = arr[gt], arr[i]
                    gt -= 1
                else:
                    i += 1
            if lt - lo < hi - gt:
                sort(lo, lt - 1)
                lo = gt + 1
            else:
                sort(gt + 1, hi)
                hi = lt - 1

    sort(0, len(arr) - 1)
    return [item for _, item in arr]


# --------------------------------------------------------------------- heap sort
def heap_sort(items: Iterable[Any], key: KeyFunc = None, reverse: bool = False) -> List[Any]:
    """힙 정렬 (불안정). 최대 힙을 만든 뒤 루트(최댓값)를 끝으로 보내는 일을 반복한다."""
    less = _make_less(reverse)
    arr = _decorate(items, key)
    n = len(arr)

    def sift_down(start: int, end: int) -> None:
        root = start
        while True:
            child = 2 * root + 1
            if child > end:
                return
            if child + 1 <= end and less(arr[child][0], arr[child + 1][0]):
                child += 1
            if less(arr[root][0], arr[child][0]):
                arr[root], arr[child] = arr[child], arr[root]
                root = child
            else:
                return

    for start in range((n - 2) // 2, -1, -1):  # 바텀업 힙 구성 O(n)
        sift_down(start, n - 1)
    for end in range(n - 1, 0, -1):
        arr[0], arr[end] = arr[end], arr[0]
        sift_down(0, end - 1)
    return [item for _, item in arr]


# --------------------------------------------------------------------- insertion sort
def insertion_sort(items: Iterable[Any], key: KeyFunc = None, reverse: bool = False) -> List[Any]:
    """삽입 정렬 (안정). 앞쪽 정렬 구간에 원소를 하나씩 끼워 넣는다.

    거의 정렬된 데이터에서는 O(n)에 가깝다. 커밋은 대부분 시간순으로 생기므로
    날짜 기준 정렬에서 실제로 빠르게 동작한다(벤치마크 참고).
    """
    less = _make_less(reverse)
    arr = _decorate(items, key)
    for i in range(1, len(arr)):
        cur = arr[i]
        j = i - 1
        while j >= 0 and less(cur[0], arr[j][0]):  # 엄격히 작을 때만 이동 → 안정
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = cur
    return [item for _, item in arr]


ALGORITHMS = {
    "merge": merge_sort,
    "quick": quick_sort,
    "heap": heap_sort,
    "insertion": insertion_sort,
}

ALGORITHM_INFO = {
    "merge": ("O(n log n)", "O(n log n)", "O(n)", True),
    "quick": ("O(n log n)", "O(n²)", "O(log n)", False),
    "heap": ("O(n log n)", "O(n log n)", "O(1)", False),
    "insertion": ("O(n²)", "O(n²)", "O(1)", True),
}
"""알고리즘별 (평균, 최악, 추가 공간, 안정 여부)"""

DEFAULT_ALGORITHM = "merge"


def sort_items(items: Iterable[Any], key: KeyFunc = None, reverse: bool = False,
               algorithm: str = DEFAULT_ALGORITHM) -> List[Any]:
    """이름으로 알고리즘을 골라 정렬한다."""
    try:
        func = ALGORITHMS[algorithm]
    except KeyError:
        raise ValueError("unknown sort algorithm: {}".format(algorithm))
    return func(items, key=key, reverse=reverse)
