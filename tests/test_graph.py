import random
import unittest

from mini_git import graph
from tests.helpers import random_dag


def brute_force_ancestors(start, parents):
    seen, stack = set(), list(parents[start])
    while stack:
        node = stack.pop()
        if node not in seen:
            seen.add(node)
            stack.extend(parents[node])
    return seen


def brute_force_best_path(src, dst, neighbors):
    """모든 최단 경로를 나열해 문자열 사전순 최소를 고른다(정답지)."""
    dist = graph.bfs_distances(src, neighbors)
    if dst not in dist:
        return None
    target_len = dist[dst]
    best = None

    def dfs(node, path):
        nonlocal best
        if len(path) - 1 > target_len:
            return
        if node == dst:
            if len(path) - 1 == target_len:
                s = "->".join(path)
                if best is None or s < best:
                    best = s
            return
        for nxt in neighbors(node):
            if nxt not in path and dist.get(nxt) == len(path):
                dfs(nxt, path + [nxt])

    dfs(src, [src])
    return best


class TopologicalOrderTest(unittest.TestCase):
    def test_parents_always_first_on_random_dags(self):
        rng = random.Random(11)
        for _ in range(50):
            names, parents, children = random_dag(rng, rng.randint(1, 40))
            order = graph.topological_order(names, parents.__getitem__, children.__getitem__,
                                            priority=lambda h: rng.random())
            self.assertEqual(len(order), len(names))
            self.assertTrue(graph.is_valid_topological_order(order, parents.__getitem__))

    def test_priority_breaks_ties(self):
        parents = {"a": (), "b": ("a",), "c": ("a",), "d": ("b", "c")}
        children = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
        prio = {"a": 0, "b": 2, "c": 1, "d": 3}
        order = graph.topological_order(parents, parents.__getitem__, children.__getitem__, prio.__getitem__)
        self.assertEqual(order, ["a", "c", "b", "d"])

    def test_cycle_is_detected(self):
        parents = {"a": ("c",), "b": ("a",), "c": ("b",), "r": ()}
        children = {"a": ["b"], "b": ["c"], "c": ["a"], "r": []}
        with self.assertRaises(graph.CycleError):
            graph.topological_order(parents, parents.__getitem__, children.__getitem__, lambda h: h)


class AncestorsTest(unittest.TestCase):
    def test_matches_brute_force_and_bfs_order(self):
        rng = random.Random(5)
        for _ in range(50):
            names, parents, _ = random_dag(rng, rng.randint(1, 40), max_parents=3)
            start = rng.choice(names)
            result = graph.ancestors(start, parents.__getitem__)
            self.assertEqual({h for h, _ in result}, brute_force_ancestors(start, parents))
            self.assertEqual(len(result), len({h for h, _ in result}))  # 중복 없음
            dists = [d for _, d in result]
            self.assertTrue(all(dists[i] <= dists[i + 1] for i in range(len(dists) - 1)))

    def test_diamond_visits_common_ancestor_once(self):
        parents = {"r": (), "a": ("r",), "b": ("r",), "m": ("a", "b")}
        self.assertEqual(graph.ancestors("m", parents.__getitem__), [("a", 1), ("b", 1), ("r", 2)])


class ShortestPathTest(unittest.TestCase):
    def test_matches_brute_force_lexicographic_minimum(self):
        rng = random.Random(9)
        for _ in range(80):
            names, parents, children = random_dag(rng, rng.randint(2, 14), max_parents=2)

            def neighbors(h):
                return list(parents[h]) + children[h]

            a, b = rng.choice(names), rng.choice(names)
            path = graph.shortest_path(a, b, neighbors)
            expected = brute_force_best_path(a, b, neighbors)
            self.assertEqual(None if path is None else "->".join(path), expected)

    def test_tie_break_by_string(self):
        #   s ─ x1 ─ t
        #   s ─ x0 ─ t     → "s->x0->t" 가 사전순으로 더 작다
        nb = {"s": ["x1", "x0"], "x0": ["s", "t"], "x1": ["s", "t"], "t": ["x0", "x1"]}
        self.assertEqual(graph.shortest_path("s", "t", nb.__getitem__), ["s", "x0", "t"])

    def test_prefix_hashes(self):
        nb = {"s": ["abcd", "abc"], "abc": ["s", "t"], "abcd": ["s", "t"], "t": ["abc", "abcd"]}
        self.assertEqual(graph.shortest_path("s", "t", nb.__getitem__), ["s", "abc", "t"])

    def test_same_node_and_no_path(self):
        nb = {"a": [], "b": []}
        self.assertEqual(graph.shortest_path("a", "a", nb.__getitem__), ["a"])
        self.assertIsNone(graph.shortest_path("a", "b", nb.__getitem__))


if __name__ == "__main__":
    unittest.main()
