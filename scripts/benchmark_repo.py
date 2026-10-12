"""커밋 수 증가에 따른 연산 비용 측정 (체크리스트 4-1 "커밋 수가 10배 늘면?"의 근거).

    python scripts/benchmark_repo.py              # 1,000 / 10,000 / 100,000 커밋
    python scripts/benchmark_repo.py 300000

브랜치 10개를 오가며 커밋하고 가끔 merge 해서 실제와 비슷한 DAG 를 만든 뒤 측정한다.
SEARCH 는 역색인 검색과 "모든 커밋 메시지를 순회하는 단순 검색"을 함께 측정해 비교한다.
"""

import os
import random
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mini_git.clock import SteppingClock  # noqa: E402
from mini_git.hashing import HashGenerator  # noqa: E402
from mini_git.index import tokenize  # noqa: E402
from mini_git.repository import Repository  # noqa: E402

WORDS = ["add", "fix", "refactor", "login", "payment", "cache", "api", "docs", "test", "build",
         "auth", "search", "index", "graph", "sort", "ui", "db", "log", "config", "deploy"]


def build(n: int, rng: random.Random) -> Repository:
    repo = Repository(clock=SteppingClock(datetime(2024, 1, 1), 30), hash_generator=HashGenerator("sha1"))
    repo.init("dev0")
    repo.commit("initial commit")
    branches = ["main"]
    while len(repo.commits) < n:
        r = rng.random()
        if r < 0.01 and len(branches) < 10:
            name = "b{}".format(len(branches))
            repo.create_branch(name)
            branches.append(name)
        elif r < 0.05:
            repo.switch(rng.choice(branches))
        elif r < 0.07:
            other = rng.choice(branches)
            if other != repo.head:
                repo.merge(other)
        else:
            repo.set_user("dev{}".format(rng.randint(0, 19)))
            repo.commit(" ".join(rng.sample(WORDS, 4)) + " #{}".format(len(repo.commits)))
    return repo


def timed(func):
    t0 = time.perf_counter()
    result = func()
    return result, (time.perf_counter() - t0) * 1000


def naive_search(repo: Repository, word: str):
    return [c for c in repo.commits.values() if word in tokenize(c.message)]


def bench(n: int):
    rng = random.Random(n)
    t0 = time.perf_counter()
    repo = build(n, rng)
    build_ms = (time.perf_counter() - t0) * 1000
    hashes = list(repo.commits)
    first, last = hashes[0], hashes[-1]
    _, log_ms = timed(lambda: repo.log_topological())
    _, sort_ms = timed(lambda: repo.log_sorted("author"))
    path, path_ms = timed(lambda: repo.path(first, last))
    anc, anc_ms = timed(lambda: repo.ancestors(last))
    hits, idx_ms = timed(lambda: repo.search_keyword("login"))
    hits2, naive_ms = timed(lambda: naive_search(repo, "login"))
    assert len(hits) == len(hits2)
    _, prefix_ms = timed(lambda: repo.resolve(last[:5]))
    return [n, round(n / (build_ms / 1000)), round(log_ms, 1), round(sort_ms, 1), len(path) - 1, round(path_ms, 1),
            len(anc), round(anc_ms, 1), len(hits), round(idx_ms, 2), round(naive_ms, 1), round(prefix_ms, 2)]


def main() -> None:
    sizes = [1_000, 10_000, 100_000] + [int(a) for a in sys.argv[1:]]
    header = ["commits", "COMMIT/s", "LOG ms", "SORT author ms", "PATH len", "PATH ms", "ancestors", "ANCESTORS ms",
              "hits", "SEARCH(index) ms", "SEARCH(scan) ms", "prefix resolve ms"]
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))
    for n in sizes:
        print("| " + " | ".join("{:,}".format(v) if isinstance(v, int) else str(v) for v in bench(n)) + " |")
    print("\nPython {} / {}".format(sys.version.split()[0], sys.platform))


if __name__ == "__main__":
    main()
