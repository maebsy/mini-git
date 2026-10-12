import random
import unittest
from collections import Counter

from mini_git import sorting

ALGOS = list(sorting.ALGORITHMS.items())


def is_nondecreasing(seq):
    return all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1))


class SortingCorrectnessTest(unittest.TestCase):
    def check(self, data, **kwargs):
        for name, algo in ALGOS:
            with self.subTest(algo=name, n=len(data)):
                out = algo(data, **kwargs)
                key = kwargs.get("key") or (lambda x: x)
                keys = [key(x) for x in out]
                if kwargs.get("reverse"):
                    keys = keys[::-1]
                self.assertTrue(is_nondecreasing(keys))
                self.assertEqual(Counter(out), Counter(data))  # 같은 원소들(순열)인지

    def test_edge_cases(self):
        for data in ([], [1], [2, 1], [1, 1, 1], [3, 1, 2]):
            self.check(data)

    def test_random_sorted_reversed_duplicates(self):
        rng = random.Random(1)
        for n in (10, 100, 1000):
            rand = [rng.randint(-1000, 1000) for _ in range(n)]
            self.check(rand)
            self.check(list(range(n)))
            self.check(list(range(n, 0, -1)))
            self.check([rng.randint(0, 3) for _ in range(n)])

    def test_key_and_reverse(self):
        words = ["banana", "Apple", "cherry", "apple", "Banana"]
        self.check(words, key=str.casefold)
        self.check(words, key=len, reverse=True)

    def test_original_list_is_not_modified(self):
        data = [3, 1, 2]
        for _, algo in ALGOS:
            algo(data)
        self.assertEqual(data, [3, 1, 2])


class StabilityTest(unittest.TestCase):
    def setUp(self):
        rng = random.Random(7)
        # (키, 원래 위치) — 키가 같으면 원래 위치 순서가 유지돼야 안정 정렬
        self.items = [(rng.randint(0, 5), i) for i in range(300)]

    def assert_stable(self, out, reverse=False):
        for a, b in zip(out, out[1:]):
            if a[0] == b[0]:
                self.assertLess(a[1], b[1])

    def test_merge_and_insertion_are_stable(self):
        for name in ("merge", "insertion"):
            with self.subTest(algo=name):
                self.assert_stable(sorting.ALGORITHMS[name](self.items, key=lambda x: x[0]))
                self.assert_stable(sorting.ALGORITHMS[name](self.items, key=lambda x: x[0], reverse=True))

    def test_quick_and_heap_are_not_stable(self):
        for name in ("quick", "heap"):
            with self.subTest(algo=name):
                out = sorting.ALGORITHMS[name](self.items, key=lambda x: x[0])
                broken = any(a[0] == b[0] and a[1] > b[1] for a, b in zip(out, out[1:]))
                self.assertTrue(broken, "이 입력에서는 불안정성이 드러나야 한다")


class KeyComputedOnceTest(unittest.TestCase):
    def test_key_called_n_times(self):
        calls = []

        def key(x):
            calls.append(x)
            return x

        for name, algo in ALGOS:
            calls.clear()
            algo(list(range(200, 0, -1)), key=key)
            self.assertEqual(len(calls), 200, name)


if __name__ == "__main__":
    unittest.main()
