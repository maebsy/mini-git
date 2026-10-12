"""테스트 공용 도구."""

import random
from datetime import datetime

from mini_git.cli import CommandRunner
from mini_git.clock import SteppingClock
from mini_git.hashing import HashGenerator
from mini_git.repository import Repository

START = datetime(2024, 1, 15, 9, 0, 0)


def make_repo(mode: str = "counter", step: float = 900, seed=None) -> Repository:
    """시각이 15분씩 증가하고 hash 가 예측 가능한 저장소."""
    return Repository(clock=SteppingClock(START, step), hash_generator=HashGenerator(mode, seed))


def make_runner(mode: str = "counter", step: float = 900) -> CommandRunner:
    return CommandRunner(make_repo(mode, step))


def random_dag(rng: random.Random, n: int, max_parents: int = 2):
    """노드 0..n-1, 각 노드는 자기보다 작은 번호 중에서 부모를 고른다 → 항상 DAG."""
    names = ["n{:03d}".format(i) for i in range(n)]
    parents = {}
    for i, name in enumerate(names):
        k = 0 if i == 0 else rng.randint(0 if rng.random() < 0.1 else 1, min(max_parents, i))
        parents[name] = tuple(rng.sample(names[:i], k)) if k else ()
    children = {name: [] for name in names}
    for name, ps in parents.items():
        for p in ps:
            children[p].append(name)
    return names, parents, children
