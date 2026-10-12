import unittest

from mini_git import graph
from mini_git.hashing import HashGenerator
from mini_git.repository import (InvalidArgs, MiniGitError, NotInitialized, Repository, UnknownBranch,
                                 UnknownCommit)
from tests.helpers import make_repo


class InitBranchSwitchTest(unittest.TestCase):
    def test_init_sets_main_head_and_user(self):
        repo = make_repo()
        self.assertTrue(repo.init("Alice"))
        self.assertEqual(repo.head, "main")
        self.assertIn("main", repo.branches)
        self.assertIsNone(repo.branches["main"])
        self.assertEqual(repo.user, "Alice")
        self.assertFalse(repo.init("Bob"))  # 재초기화는 사용자만 변경
        self.assertEqual(repo.user, "Bob")

    def test_commands_before_init_fail(self):
        repo = make_repo()
        with self.assertRaises(NotInitialized):
            repo.commit("x")

    def test_branch_points_to_head_and_commits_follow_switch(self):
        repo = make_repo()
        repo.init("Alice")
        root = repo.commit("Initial commit")
        self.assertEqual(repo.create_branch("feature"), root.hash)
        repo.switch("feature")
        c = repo.commit("Add login feature")
        self.assertEqual(c.parents, (root.hash,))
        self.assertEqual(repo.branches["feature"], c.hash)
        self.assertEqual(repo.branches["main"], root.hash)  # main 은 그대로
        self.assertEqual(c.branch, "feature")

    def test_branch_errors(self):
        repo = make_repo()
        repo.init("Alice")
        with self.assertRaises(MiniGitError):
            repo.create_branch("feature")  # 커밋 없음
        repo.commit("first")
        repo.create_branch("feature")
        with self.assertRaises(MiniGitError):
            repo.create_branch("feature")  # 중복
        with self.assertRaises(UnknownBranch):
            repo.switch("nope")
        with self.assertRaises(InvalidArgs):
            repo.create_branch("has space")

    def test_orphan_branch_creates_new_root(self):
        repo = make_repo()
        repo.init("Alice")
        repo.commit("main root")
        repo.switch("docs", orphan=True)
        c = repo.commit("docs root")
        self.assertEqual(c.parents, ())


class HashTest(unittest.TestCase):
    def test_hashes_unique_in_all_modes(self):
        for mode in ("sha1", "counter", "random"):
            repo = make_repo(mode=mode)
            repo.init("Alice")
            hashes = {repo.commit("same message").hash for _ in range(500)}
            self.assertEqual(len(hashes), 500, mode)

    def test_counter_mode_is_sequential(self):
        repo = make_repo(mode="counter")
        repo.init("A")
        self.assertEqual([repo.commit("m").hash for _ in range(3)], ["0000001", "0000002", "0000003"])

    def test_random_mode_reproducible_with_seed(self):
        def hashes(seed):
            repo = make_repo(mode="random", seed=seed)
            repo.init("A")
            return [repo.commit("m").hash for _ in range(5)]
        self.assertEqual(hashes(42), hashes(42))
        self.assertNotEqual(hashes(42), hashes(43))

    def test_sha1_mode_is_deterministic_for_same_inputs(self):
        def hashes():
            repo = make_repo(mode="sha1")
            repo.init("A")
            return [repo.commit("m{}".format(i)).hash for i in range(5)]
        self.assertEqual(hashes(), hashes())

    def test_collision_is_resolved_by_extending(self):
        gen = HashGenerator("sha1")
        taken = {"abcdef1"}
        h = gen._extend("abcdef1234", taken.__contains__, 0)
        self.assertEqual(h, "abcdef12")
        self.assertEqual(gen.collisions, 1)


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo(mode="counter")
        self.repo.init("Alice")
        self.c1 = self.repo.commit("one")
        self.repo.create_branch("feature")

    def test_full_prefix_and_branch(self):
        self.assertEqual(self.repo.resolve(self.c1.hash), self.c1.hash)
        self.assertEqual(self.repo.resolve("feature"), self.c1.hash)
        self.assertEqual(self.repo.resolve("00000"), self.c1.hash)  # 유일한 축약형

    def test_unknown_and_ambiguous(self):
        with self.assertRaises(UnknownCommit):
            self.repo.resolve("zzzz")
        self.repo.commit("two")
        with self.assertRaises(MiniGitError):
            self.repo.resolve("00000")  # 0000001, 0000002 둘 다 매칭


class LogTest(unittest.TestCase):
    def setUp(self):
        repo = make_repo()
        repo.init("Carol")
        self.root = repo.commit("root")
        repo.create_branch("feature")
        repo.set_user("Alice")
        self.m1 = repo.commit("main 1")
        repo.switch("feature")
        repo.set_user("Bob")
        self.f1 = repo.commit("feature 1")
        repo.set_user("Alice")
        self.f2 = repo.commit("feature 2")
        self.repo = repo

    def test_topological_log_parents_first(self):
        order = [c.hash for c in self.repo.log_topological()]
        self.assertTrue(graph.is_valid_topological_order(order, self.repo.parents_of))
        self.assertEqual(order, [self.root.hash, self.m1.hash, self.f1.hash, self.f2.hash])

    def test_sort_by_date(self):
        out = [c.hash for c in self.repo.log_sorted("date")]
        self.assertEqual(out, [self.root.hash, self.m1.hash, self.f1.hash, self.f2.hash])

    def test_sort_by_author_is_stable_by_time(self):
        out = [(c.author, c.message) for c in self.repo.log_sorted("author")]
        self.assertEqual(out, [("Alice", "main 1"), ("Alice", "feature 2"), ("Bob", "feature 1"), ("Carol", "root")])

    def test_author_topo_keeps_parent_first(self):
        out = [c.message for c in self.repo.log_topological("author")]
        # 작성자순이면 Carol(root)이 마지막이어야 하지만 root 는 모든 커밋의 조상이라 맨 앞
        self.assertEqual(out[0], "root")
        self.assertTrue(graph.is_valid_topological_order(
            [c.hash for c in self.repo.log_topological("author")], self.repo.parents_of))

    def test_same_timestamp_ties_use_creation_order(self):
        repo = make_repo(step=0)  # 모든 커밋이 같은 시각
        repo.init("A")
        hashes = [repo.commit("c{}".format(i)).hash for i in range(10)]
        self.assertEqual([c.hash for c in repo.log_sorted("date")], hashes)
        self.assertEqual([c.hash for c in repo.log_topological()], hashes)


class DagInvariantTest(unittest.TestCase):
    def test_graph_is_always_acyclic(self):
        import random
        rng = random.Random(3)
        repo = make_repo()
        repo.init("A")
        repo.commit("root")
        branches = ["main"]
        for i in range(300):
            op = rng.random()
            if op < 0.15:
                name = "b{}".format(i)
                repo.create_branch(name)
                branches.append(name)
            elif op < 0.35:
                repo.switch(rng.choice(branches))
            else:
                repo.commit("c{}".format(i))
        order = [c.hash for c in repo.log_topological()]  # 사이클이 있으면 CycleError
        self.assertEqual(len(order), len(repo.commits))
        self.assertTrue(graph.is_valid_topological_order(order, repo.parents_of))


if __name__ == "__main__":
    unittest.main()
