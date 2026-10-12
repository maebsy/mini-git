"""커밋 그래프 알고리즘.

그래프 표현
-----------
* 방향 간선은 **자식 → 부모** (커밋이 부모를 가리킨다). 부모 목록은 ``Commit.parents`` 에 있다.
* 역방향(부모 → 자식) 탐색을 위해 저장소가 ``children`` 인접 리스트를 따로 유지한다.

알고리즘은 저장소 클래스를 모르고 **이웃을 알려주는 함수**만 받는다.

* ``parents_of(hash)``  → 부모 hash 목록 (ANCESTORS, 위상 정렬)
* ``children_of(hash)`` → 자식 hash 목록 (위상 정렬)
* ``neighbors_of(hash)``→ 부모 + 자식 (PATH 의 무방향 간선)

이렇게 분리하면 같은 BFS 코드를 "부모 방향만" / "무방향" 탐색에 재사용할 수 있고,
가짜 그래프로 단위 테스트하기도 쉽다. (그래프 전용 라이브러리 사용 금지 제약 대응)
"""

from collections import deque
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .priority_queue import PriorityQueue

Neighbors = Callable[[str], Sequence[str]]


class CycleError(Exception):
    """그래프에 사이클이 있어 위상 순서를 정할 수 없을 때 발생한다."""


# --------------------------------------------------------------------------- BFS
def bfs_distances(start: str, neighbors_of: Neighbors) -> Dict[str, int]:
    """``start`` 에서 각 노드까지의 최단 간선 수. 도달 못 하는 노드는 결과에 없다.

    BFS 는 거리 0, 1, 2 … 순서로 한 겹씩 넓혀가므로 처음 방문한 순간의 거리가 최단 거리다.
    방문 표시(dist 딕셔너리)가 있어 같은 노드를 두 번 넣지 않는다 → O(V + E).
    """
    dist = {start: 0}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for nxt in neighbors_of(node):
            if nxt not in dist:
                dist[nxt] = dist[node] + 1
                queue.append(nxt)
    return dist


def ancestors(start: str, parents_of: Neighbors) -> List[Tuple[str, int]]:
    """``start`` 에서 부모 방향으로 도달 가능한 모든 조상과 거리 (자기 자신 제외).

    가까운 조상부터(BFS 순서) 반환한다. merge 커밋 때문에 같은 조상에 여러 경로로
    도달할 수 있지만 방문 표시 덕분에 한 번만 나온다.
    """
    dist = bfs_distances(start, parents_of)
    order: List[Tuple[str, int]] = []
    # bfs_distances 는 방문 순서대로 dist 에 삽입하므로(dict 는 삽입 순서 유지) 그대로 BFS 순서다.
    for node, d in dist.items():
        if node != start:
            order.append((node, d))
    return order


def shortest_path(source: str, target: str, neighbors_of: Neighbors) -> Optional[List[str]]:
    """간선 수가 최소인 경로. 여러 개면 ``"h1->h2->..."`` 문자열이 사전순으로 가장 작은 경로.

    방법
    1) **target 에서** BFS 를 돌려 모든 노드의 'target 까지 남은 거리'를 구한다.
    2) source 에서 출발해, 매 단계 '남은 거리가 정확히 1 줄어드는 이웃' 중
       hash 가 사전순으로 가장 작은 것을 고른다(greedy).

    2)가 전체 경로 문자열의 사전순 최소를 보장하는 이유: 후보 경로들은 앞부분이 같고
    처음 갈라지는 지점의 hash 에서 비교가 결정된다. 그 지점에서 가장 작은 hash 를 고르면
    그 뒤가 무엇이든 문자열 비교에서 이긴다. (hash 는 서로 다르고, 짧은 hash 가 긴 hash 의
    접두사인 경우에도 구분자 '-' 가 16진수 문자보다 작아 결론이 같다.)
    또한 1)의 거리 조건 때문에 고른 이웃에서 항상 최단 거리로 target 에 도달할 수 있다.

    시간 복잡도 O(V + E), 경로가 없으면 None.
    """
    remaining = bfs_distances(target, neighbors_of)
    if source not in remaining:
        return None
    path = [source]
    node = source
    while node != target:
        want = remaining[node] - 1
        best: Optional[str] = None
        for nxt in neighbors_of(node):
            if remaining.get(nxt) == want and (best is None or nxt < best):
                best = nxt
        assert best is not None  # BFS 거리 정의상 반드시 존재
        path.append(best)
        node = best
    return path


# --------------------------------------------------------------------- 위상 정렬
def topological_order(
    nodes: Iterable[str],
    parents_of: Neighbors,
    children_of: Neighbors,
    priority: Callable[[str], Any],
) -> List[str]:
    """부모가 항상 자식보다 먼저 나오는 순서 (Kahn 알고리즘).

    1) 각 커밋의 진입 차수 = 부모 수. 부모가 없는 루트 커밋부터 '출력 가능' 집합에 넣는다.
    2) 출력 가능 집합에서 ``priority`` 가 가장 작은 커밋을 꺼내 출력한다. (우선순위 큐)
    3) 그 커밋의 자식들의 진입 차수를 1 줄이고, 0 이 된 자식(=부모를 모두 출력한 자식)을 넣는다.
    4) 출력한 개수가 전체보다 적으면 사이클이 있다는 뜻이므로 CycleError.

    ``priority`` 를 바꾸면 "부모 우선" 제약을 지키면서 2차 기준을 바꿀 수 있다.
    * (timestamp, seq) → 같은 조건이면 오래된 커밋 먼저 (LOG 기본)
    * (author, timestamp, seq) → 작성자순을 최대한 따르되 부모-자식 순서는 절대 어기지 않음

    시간 복잡도 O((V + E) log V).
    """
    node_list = list(nodes)
    indegree = {h: len(parents_of(h)) for h in node_list}
    ready = PriorityQueue()
    for h in node_list:
        if indegree[h] == 0:
            ready.push(priority(h), h)
    order: List[str] = []
    while len(ready):
        h = ready.pop()
        order.append(h)
        for child in children_of(h):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.push(priority(child), child)
    if len(order) != len(node_list):
        stuck = [h for h in node_list if indegree[h] > 0]
        raise CycleError("cycle detected among commits: {}".format(", ".join(stuck)))
    return order


def is_valid_topological_order(order: Sequence[str], parents_of: Neighbors) -> bool:
    """모든 커밋에 대해 부모가 먼저 나왔는지 검사한다(테스트·검증용)."""
    position = {h: i for i, h in enumerate(order)}
    return all(position[p] < position[h] for h in order for p in parents_of(h))
