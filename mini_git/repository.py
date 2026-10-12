"""저장소: 커밋 저장소 · 브랜치 · HEAD · 사용자 정보를 관리한다.

책임 분리
=========================  =====================================================
구성 요소                    역할
=========================  =====================================================
``commits`` (dict)          hash → Commit. 커밋 조회를 평균 O(1)로 (해시맵 기반)
``children`` (dict)         hash → [자식 hash]. 부모→자식 방향 탐색(위상 정렬, PATH)용
``branches`` (dict)         브랜치 이름 → 끝 커밋 hash (커밋이 없으면 None)
``head`` (str)              현재 브랜치 이름. HEAD 는 '브랜치'를 가리키고, 브랜치가 '커밋'을 가리킨다
``user`` (str)              현재 작성자
``index`` (InvertedIndex)   keyword/author → 커밋 목록
=========================  =====================================================

알고리즘(그래프 탐색·정렬)은 ``graph.py`` / ``sorting.py`` 에 있고, 이 클래스는 데이터를 넘겨주기만 한다.
"""

from typing import Dict, List, Optional, Sequence, Tuple

from . import graph, sorting
from .clock import SystemClock
from .hashing import HashGenerator
from .index import InvertedIndex, normalize_author
from .models import Commit

MIN_PREFIX = 4  # 축약 hash 로 인정하는 최소 길이


class MiniGitError(Exception):
    """사용자에게 그대로 보여줄 에러."""


class InvalidArgs(MiniGitError):
    def __init__(self, detail: str = "") -> None:
        super().__init__("Invalid args" + (": " + detail if detail else ""))


class UnknownBranch(MiniGitError):
    def __init__(self, name: str) -> None:
        super().__init__("Unknown branch: {}".format(name))


class UnknownCommit(MiniGitError):
    def __init__(self, ref: str) -> None:
        super().__init__("Unknown commit: {}".format(ref))


class NotInitialized(MiniGitError):
    def __init__(self) -> None:
        super().__init__("Not initialized. Run: INIT <user_name>")


def _validate_name(name: str, what: str) -> str:
    name = name.strip()
    if not name or any(ch.isspace() for ch in name):
        raise InvalidArgs("{} must be a non-empty word without spaces".format(what))
    return name


class Repository:
    """메모리 위에서 동작하는 Mini Git 저장소."""

    DEFAULT_BRANCH = "main"

    def __init__(self, clock=None, hash_generator: Optional[HashGenerator] = None) -> None:
        self.clock = clock or SystemClock()
        self.hasher = hash_generator or HashGenerator()
        self.initialized = False
        self.user = ""
        self.commits: Dict[str, Commit] = {}
        self.children: Dict[str, List[str]] = {}
        self.branches: Dict[str, Optional[str]] = {}
        self.head = self.DEFAULT_BRANCH
        self.index = InvertedIndex()
        self._seq = 0

    # ================================================================ 내부 헬퍼
    def _require_init(self) -> None:
        if not self.initialized:
            raise NotInitialized()

    def parents_of(self, h: str) -> Tuple[str, ...]:
        return self.commits[h].parents

    def children_of(self, h: str) -> List[str]:
        return self.children.get(h, [])

    def neighbors_of(self, h: str) -> List[str]:
        """PATH 용 무방향 이웃: 부모 + 자식"""
        return list(self.commits[h].parents) + self.children.get(h, [])

    @property
    def head_commit(self) -> Optional[str]:
        return self.branches.get(self.head)

    def _new_commit(self, message: str, parents: Sequence[str]) -> Commit:
        timestamp = self.clock.now()
        payload = "\0".join([str(self._seq), self.user, timestamp.isoformat(), message] + list(parents))
        h = self.hasher.generate(payload, self._seq, lambda c: c in self.commits)
        commit = Commit(h, message, self.user, timestamp, tuple(parents), self._seq, self.head)
        self._seq += 1
        # 저장 → 그래프 역방향 간선 → 브랜치 이동 → 역색인 갱신 (커밋 생성과 같은 시점)
        self.commits[h] = commit
        self.children[h] = []
        for p in parents:
            self.children[p].append(h)
        self.branches[self.head] = h
        self.index.add(h, message, self.user)
        return commit

    # ================================================================ 저장소/브랜치
    def init(self, user: str) -> bool:
        """저장소 초기화. 이미 초기화돼 있으면 False 를 반환하고 사용자만 바꾼다."""
        user = " ".join(user.split())
        if not user:
            raise InvalidArgs("user name is required")
        already = self.initialized
        self.user = user
        if not already:
            self.initialized = True
            self.branches[self.DEFAULT_BRANCH] = None
            self.head = self.DEFAULT_BRANCH
        return not already

    def set_user(self, user: str) -> None:
        self._require_init()
        user = " ".join(user.split())
        if not user:
            raise InvalidArgs("user name is required")
        self.user = user

    def create_branch(self, name: str) -> str:
        """현재 HEAD 커밋을 가리키는 새 브랜치를 만든다."""
        self._require_init()
        name = _validate_name(name, "branch name")
        if name in self.branches:
            raise MiniGitError("Branch already exists: {}".format(name))
        if self.head_commit is None:
            raise MiniGitError("Cannot create branch '{}': no commits yet on '{}'".format(name, self.head))
        self.branches[name] = self.head_commit
        return self.head_commit

    def switch(self, name: str, orphan: bool = False) -> None:
        """HEAD 를 다른 브랜치로 옮긴다. ``orphan=True`` 면 커밋이 없는 새 브랜치를 만든다."""
        self._require_init()
        name = _validate_name(name, "branch name")
        if orphan:
            if name in self.branches:
                raise MiniGitError("Branch already exists: {}".format(name))
            self.branches[name] = None
        elif name not in self.branches:
            raise UnknownBranch(name)
        self.head = name

    def commit(self, message: str) -> Commit:
        """현재 HEAD 커밋을 부모로 하는 새 커밋. 첫 커밋은 부모가 없는 루트 커밋."""
        self._require_init()
        message = message.strip()
        if not message:
            raise InvalidArgs("commit message is required")
        parent = self.head_commit
        return self._new_commit(message, [parent] if parent else [])

    def merge(self, branch: str) -> Tuple[str, Optional[Commit]]:
        """[보너스] 대상 브랜치를 현재 브랜치에 병합한다.

        반환: (상태, 커밋) — 상태는 "merged" | "up-to-date" | "fast-forward"
        * 대상이 현재 HEAD 의 조상이면 이미 반영됨 → 커밋 생성 안 함
        * 현재 브랜치에 커밋이 없으면 대상 커밋으로 fast-forward
        * 그 외에는 부모가 2개(현재 HEAD, 대상 HEAD)인 merge commit 생성
        """
        self._require_init()
        if branch not in self.branches:
            raise UnknownBranch(branch)
        if branch == self.head:
            raise MiniGitError("Cannot merge a branch into itself: {}".format(branch))
        theirs = self.branches[branch]
        ours = self.head_commit
        if theirs is None:
            raise MiniGitError("Nothing to merge: branch '{}' has no commits".format(branch))
        if ours is None:
            self.branches[self.head] = theirs
            return "fast-forward", self.commits[theirs]
        if graph.is_ancestor(theirs, ours, self.parents_of):
            return "up-to-date", None
        message = "Merge branch '{}' into {}".format(branch, self.head)
        return "merged", self._new_commit(message, [ours, theirs])

    # ================================================================ 조회
    def resolve(self, ref: str) -> str:
        """참조 문자열을 커밋 hash 로 바꾼다.

        순서: 전체 hash → 브랜치 이름 → 축약 hash(4자 이상, 유일할 때만)
        """
        self._require_init()
        if ref in self.commits:
            return ref
        if ref in self.branches:
            tip = self.branches[ref]
            if tip is None:
                raise UnknownCommit(ref)
            return tip
        if len(ref) >= MIN_PREFIX:
            matches = [h for h in self.commits if h.startswith(ref)]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise MiniGitError("Ambiguous commit: {} (matches {})".format(ref, ", ".join(matches)))
        raise UnknownCommit(ref)

    def branches_at(self, h: str) -> List[str]:
        return [name for name, tip in self.branches.items() if tip == h]

    def date_key(self, h: str):
        c = self.commits[h]
        return (c.timestamp, c.seq)

    def author_key(self, h: str):
        c = self.commits[h]
        return (normalize_author(c.author), c.timestamp, c.seq)

    def log_topological(self, priority: str = "date") -> List[Commit]:
        """부모가 항상 자식보다 먼저 나오는 LOG. priority 는 같은 조건일 때의 2차 기준."""
        self._require_init()
        key = self.author_key if priority == "author" else self.date_key
        order = graph.topological_order(self.commits.keys(), self.parents_of, self.children_of, key)
        return [self.commits[h] for h in order]

    def log_sorted(self, by: str, algorithm: str = sorting.DEFAULT_ALGORITHM) -> List[Commit]:
        """LOG --sort-by=date|author. 직접 구현한 정렬 알고리즘 사용.

        * date  : (timestamp, seq) 오름차순 — 같은 초에 만든 커밋은 생성 순서
        * author: 작성자 이름(대소문자 무시) 오름차순 — 같은 작성자 안에서는 시간순.
                  기본 알고리즘(merge)은 안정 정렬이라, 시간순 목록을 작성자 기준으로 정렬하면
                  같은 작성자의 시간 순서가 그대로 유지된다.
        """
        self._require_init()
        commits = sorting.merge_sort(self.commits.values(), key=lambda c: (c.timestamp, c.seq))
        if by == "date":
            if algorithm == sorting.DEFAULT_ALGORITHM:
                return commits
            return sorting.sort_items(self.commits.values(), key=lambda c: (c.timestamp, c.seq), algorithm=algorithm)
        if by == "author":
            return sorting.sort_items(commits, key=lambda c: normalize_author(c.author), algorithm=algorithm)
        raise InvalidArgs("--sort-by must be date or author")

    def path(self, a: str, b: str) -> Optional[List[str]]:
        self._require_init()
        return graph.shortest_path(self.resolve(a), self.resolve(b), self.neighbors_of)

    def ancestors(self, ref: str) -> List[Tuple[Commit, int]]:
        self._require_init()
        start = self.resolve(ref)
        return [(self.commits[h], d) for h, d in graph.ancestors(start, self.parents_of)]

    def search_keyword(self, keyword: str) -> List[Commit]:
        self._require_init()
        return [self.commits[h] for h in self.index.search_keyword(keyword)]

    def search_author(self, name: str) -> List[Commit]:
        self._require_init()
        return [self.commits[h] for h in self.index.search_author(name)]
