"""이진 최소 힙 기반 우선순위 큐.

위상 정렬(Kahn 알고리즘)에서 "지금 출력할 수 있는 커밋들" 중 우선순위(예: 오래된 시각)가
가장 높은 것을 O(log n)에 꺼내기 위해 사용한다. ``heapq`` 같은 표준 정렬 관련 API 대신 직접 구현했다.

원소는 ``(priority, item)`` 쌍으로 넣는다. priority 끼리만 비교하므로 item 은 비교 불가능해도 된다.
priority 가 같은 경우를 대비해 삽입 순번을 함께 저장해 항상 결정적인 순서를 보장한다.
"""

from typing import Any, List, Tuple


class PriorityQueue:
    """``push(priority, item)`` / ``pop() -> item`` 최소 힙."""

    def __init__(self) -> None:
        self._heap: List[Tuple[Any, int, Any]] = []
        self._counter = 0

    def __len__(self) -> int:
        return len(self._heap)

    def push(self, priority: Any, item: Any) -> None:
        self._heap.append((priority, self._counter, item))
        self._counter += 1
        i = len(self._heap) - 1
        while i > 0:  # sift-up
            parent = (i - 1) // 2
            if self._heap[i][:2] < self._heap[parent][:2]:
                self._heap[i], self._heap[parent] = self._heap[parent], self._heap[i]
                i = parent
            else:
                break

    def pop(self) -> Any:
        if not self._heap:
            raise IndexError("pop from empty priority queue")
        top = self._heap[0]
        last = self._heap.pop()
        if self._heap:
            self._heap[0] = last
            i, n = 0, len(self._heap)
            while True:  # sift-down
                left, right, smallest = 2 * i + 1, 2 * i + 2, i
                if left < n and self._heap[left][:2] < self._heap[smallest][:2]:
                    smallest = left
                if right < n and self._heap[right][:2] < self._heap[smallest][:2]:
                    smallest = right
                if smallest == i:
                    break
                self._heap[i], self._heap[smallest] = self._heap[smallest], self._heap[i]
                i = smallest
        return top[2]
