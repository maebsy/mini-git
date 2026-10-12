"""명령어 해석과 출력 형식.

문법 표준
* 명령어는 대소문자를 구분하지 않는다 (``INIT`` = ``init``)
* 공백이 있는 인자는 따옴표로 감싼다 (``COMMIT "Add login feature"``)
  - 큰따옴표 안에서는 ``\\"`` 로 따옴표를 쓸 수 있고, 그 외 역슬래시는 그대로 둔다(Windows 경로 대응)
* 옵션은 ``--name=value`` 형식 (``SEARCH --author=Alice``, ``LOG --sort-by=date``)
* 표준 에러: ``Invalid args`` / ``Unknown branch: <name>`` / ``Unknown commit: <hash>``

COMMIT / SEARCH / INIT / USER 처럼 자유 문자열을 받는 명령은 따옴표 없이 여러 단어를 써도
공백으로 이어 붙여 하나의 인자로 받는다(입력 편의). 공백을 정확히 보존하려면 따옴표를 쓴다.
"""

from typing import Callable, Dict, List, Optional, Tuple

from . import diff as diff_mod
from . import sorting
from .models import Commit
from .repository import InvalidArgs, MiniGitError, Repository


class TokenizeError(Exception):
    pass


def tokenize(line: str) -> List[str]:
    """따옴표를 지원하는 토크나이저."""
    tokens: List[str] = []
    buf: List[str] = []
    in_token = False
    quote: Optional[str] = None
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if quote:
            if ch == "\\" and quote == '"' and i + 1 < n and line[i + 1] in '"\\':
                buf.append(line[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            else:
                buf.append(ch)
        elif ch in "\"'":
            quote = ch
            in_token = True
        elif ch.isspace():
            if in_token:
                tokens.append("".join(buf))
                buf, in_token = [], False
        else:
            buf.append(ch)
            in_token = True
        i += 1
    if quote:
        raise TokenizeError("unbalanced quotes")
    if in_token:
        tokens.append("".join(buf))
    return tokens


def split_options(args: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """``--key=value`` / ``--flag`` 를 옵션으로, 나머지를 위치 인자로 나눈다."""
    positional: List[str] = []
    options: Dict[str, str] = {}
    for arg in args:
        if arg.startswith("--") and len(arg) > 2:
            name, sep, value = arg[2:].partition("=")
            options[name.lower()] = value if sep else ""
        else:
            positional.append(arg)
    return positional, options


# ------------------------------------------------------------------ 출력 형식
def format_commit_header(repo: Repository, c: Commit, decorate: bool = True) -> str:
    """``commit <hash> (<author>, <time>) [<branch>]`` + 브랜치 끝이면 ``(HEAD -> main)`` 표시."""
    line = "commit {} ({}, {}) [{}]".format(c.hash, c.author, c.time_str(), c.branch)
    if decorate:
        refs = []
        for name in repo.branches_at(c.hash):
            refs.append("HEAD -> " + name if name == repo.head else name)
        refs_sorted = sorting.merge_sort(refs, key=lambda r: (not r.startswith("HEAD"), r))
        if refs_sorted:
            line += " ({})".format(", ".join(refs_sorted))
    return line


def format_log(repo: Repository, commits: List[Commit], decorate: bool = True) -> List[str]:
    """커밋 목록을 LOG 출력 줄로 만든다. merge 커밋은 ``Merge: p1 p2`` 줄을 추가한다."""
    lines: List[str] = []
    for c in commits:
        lines.append(format_commit_header(repo, c, decorate))
        if c.is_merge:
            lines.append("Merge: " + " ".join(c.parents))
        lines.append(c.message)
    return lines


def format_search(commits: List[Commit]) -> List[str]:
    """SEARCH 결과 출력: ``Found N commit(s):`` + ``- hash: message``."""
    noun = "commit" if len(commits) == 1 else "commits"
    if not commits:
        return ["Found 0 commits."]
    lines = ["Found {} {}:".format(len(commits), noun)]
    lines.extend("- {}: {} ({}, {})".format(c.hash, c.message, c.author, c.time_str()) for c in commits)
    return lines


# ------------------------------------------------------------------ 명령어 실행기
class CommandRunner:
    """한 줄 명령을 실행해 출력 줄 목록을 반환한다."""

    def __init__(self, repo: Optional[Repository] = None) -> None:
        self.repo = repo or Repository()
        self._handlers: Dict[str, Callable[[List[str]], List[str]]] = {
            "init": self.cmd_init,
            "user": self.cmd_user,
            "branch": self.cmd_branch,
            "switch": self.cmd_switch,
            "commit": self.cmd_commit,
            "log": self.cmd_log,
            "path": self.cmd_path,
            "ancestors": self.cmd_ancestors,
            "search": self.cmd_search,
            "status": self.cmd_status,
            "merge": self.cmd_merge,
            "diff": self.cmd_diff,
            "help": self.cmd_help,
        }

    def execute(self, line: str) -> List[str]:
        try:
            tokens = tokenize(line)
        except TokenizeError:
            return ["Invalid args: unbalanced quotes"]
        if not tokens:
            return []
        name, args = tokens[0].lower(), tokens[1:]
        handler = self._handlers.get(name)
        if handler is None:
            return ["Unknown command: {} (type HELP)".format(tokens[0])]
        try:
            return handler(args)
        except MiniGitError as exc:
            return [str(exc)]

    def _free_text(self, args: List[str]) -> str:
        """자유 문자열 인자: 여러 토큰이면 공백으로 이어 붙인다."""
        if not args:
            raise InvalidArgs()
        return " ".join(args)

    # ------------------------------------------------------------ 저장소/브랜치
    def cmd_init(self, args: List[str]) -> List[str]:
        user = self._free_text(args)
        created = self.repo.init(user)
        if created:
            return ["Initialized repository.", "Current branch: {}".format(self.repo.head),
                    "Current user: {}".format(self.repo.user)]
        return ["Repository already initialized.", "Current user: {}".format(self.repo.user)]

    def cmd_user(self, args: List[str]) -> List[str]:
        if args:
            self.repo.set_user(self._free_text(args))
        else:
            self.repo._require_init()  # noqa: SLF001
        return ["Current user: {}".format(self.repo.user)]

    def cmd_branch(self, args: List[str]) -> List[str]:
        if not args:  # 목록
            self.repo._require_init()  # noqa: SLF001
            lines = []
            for name in sorting.merge_sort(self.repo.branches.keys()):
                tip = self.repo.branches[name]
                marker = "*" if name == self.repo.head else " "
                if tip is None:
                    lines.append("{} {:<12} (no commits)".format(marker, name))
                else:
                    lines.append("{} {:<12} {} {}".format(marker, name, tip, self.repo.commits[tip].message))
            return lines
        if len(args) != 1:
            raise InvalidArgs()
        self.repo.create_branch(args[0])
        return ["Created branch: {}".format(args[0])]

    def cmd_switch(self, args: List[str]) -> List[str]:
        positional, options = split_options(args)
        if len(positional) != 1 or set(options) - {"orphan"}:
            raise InvalidArgs()
        if "orphan" in options:
            self.repo.switch(positional[0], orphan=True)
            return ["Switched to a new orphan branch: {}".format(positional[0])]
        self.repo.switch(positional[0])
        return ["Switched to branch: {}".format(positional[0])]

    def cmd_commit(self, args: List[str]) -> List[str]:
        c = self.repo.commit(self._free_text(args))
        return ["[{} {}] {}".format(self.repo.head, c.hash, c.message)]

    def cmd_status(self, args: List[str]) -> List[str]:
        if args:
            raise InvalidArgs()
        r = self.repo
        r._require_init()  # noqa: SLF001
        tip = r.head_commit
        stats = r.index.stats()
        return [
            "On branch {}".format(r.head),
            "HEAD: {}".format("{} {}".format(tip, r.commits[tip].message) if tip else "(no commits)"),
            "User: {}".format(r.user),
            "Commits: {} / Branches: {}".format(len(r.commits), len(r.branches)),
            "Index: {} keywords, {} authors".format(stats["keywords"], stats["authors"]),
            "Hash mode: {}".format(r.hasher.mode),
        ]

    # ------------------------------------------------------------ 로그/탐색
    def cmd_log(self, args: List[str]) -> List[str]:
        positional, options = split_options(args)
        if positional or set(options) - {"sort-by", "algo", "topo"}:
            raise InvalidArgs()
        self.repo._require_init()  # noqa: SLF001
        if not self.repo.commits:
            return ["No commits yet."]
        sort_by = options.get("sort-by")
        algo = options.get("algo", sorting.DEFAULT_ALGORITHM)
        if algo not in sorting.ALGORITHMS:
            raise InvalidArgs("--algo must be one of " + "|".join(sorting.ALGORITHMS))
        if sort_by is None:
            if "topo" in options or "algo" in options:
                raise InvalidArgs("--topo/--algo need --sort-by")
            return format_log(self.repo, self.repo.log_topological("date"))
        if sort_by not in ("date", "author"):
            raise InvalidArgs("--sort-by must be date or author")
        if "topo" in options:
            # 확장: 정렬 기준을 따르되 "부모가 자식보다 먼저" 제약은 유지 (우선순위 위상 정렬)
            return format_log(self.repo, self.repo.log_topological(sort_by))
        return format_log(self.repo, self.repo.log_sorted(sort_by, algo), decorate=False)

    def cmd_path(self, args: List[str]) -> List[str]:
        if len(args) != 2:
            raise InvalidArgs()
        path = self.repo.path(args[0], args[1])
        if path is None:
            return ["No path"]
        edges = len(path) - 1
        return ["Path: " + " -> ".join(path), "({} edge{})".format(edges, "" if edges == 1 else "s")]

    def cmd_ancestors(self, args: List[str]) -> List[str]:
        if len(args) != 1:
            raise InvalidArgs()
        start = self.repo.resolve(args[0])
        found = self.repo.ancestors(start)
        if not found:
            return ["Ancestors of {}: none (root commit)".format(start)]
        lines = ["Ancestors of {} ({}):".format(start, len(found))]
        for c, d in found:
            lines.append("- {} [distance {}] ({}, {}) {}".format(c.hash, d, c.author, c.time_str(), c.message))
        return lines

    def cmd_search(self, args: List[str]) -> List[str]:
        positional, options = split_options(args)
        if options:
            if positional or set(options) != {"author"} or not options["author"].strip():
                raise InvalidArgs()
            return format_search(self.repo.search_author(options["author"]))
        return format_search(self.repo.search_keyword(self._free_text(positional)))

    # ------------------------------------------------------------ 보너스
    def cmd_merge(self, args: List[str]) -> List[str]:
        if len(args) != 1:
            raise InvalidArgs()
        status, c = self.repo.merge(args[0])
        if status == "up-to-date":
            return ["Already up to date."]
        if status == "fast-forward":
            return ["Fast-forward: {} -> {}".format(self.repo.head, c.hash)]
        return ["[{} {}] {}".format(self.repo.head, c.hash, c.message),
                "Parents: {} (HEAD), {} ({})".format(c.parents[0], c.parents[1], args[0])]

    def cmd_diff(self, args: List[str]) -> List[str]:
        if len(args) != 2:
            raise InvalidArgs()
        try:
            a = diff_mod.read_lines(args[0])
            b = diff_mod.read_lines(args[1])
        except FileNotFoundError as exc:
            raise MiniGitError("File not found: {}".format(exc.filename))
        except (OSError, UnicodeDecodeError) as exc:
            raise MiniGitError("Cannot read file: {}".format(exc))
        return diff_mod.render_diff(args[0], args[1], diff_mod.diff_lines(a, b))

    def cmd_help(self, args: List[str]) -> List[str]:
        return HELP_TEXT.splitlines()


HELP_TEXT = """\
# 저장소 / 브랜치
  INIT <user_name>                  저장소 초기화 (main 브랜치, HEAD, 사용자 설정)
  BRANCH [<branch_name>]            현재 HEAD 에 새 브랜치 생성 (인자 없으면 목록)
  SWITCH <branch_name>              HEAD 를 브랜치로 이동 (--orphan: 빈 브랜치 생성)
  COMMIT <message>                  현재 HEAD 를 부모로 하는 커밋 생성
  USER [<name>]                     현재 작성자 확인/변경 (확장)
  STATUS                            현재 브랜치·HEAD·사용자 요약 (확장)
# 로그 / 탐색
  LOG                               부모가 자식보다 먼저 나오는 위상 정렬 순서
  LOG --sort-by=date|author         직접 구현한 병합 정렬로 정렬 (--algo=merge|quick|heap|insertion)
  LOG --sort-by=author --topo       작성자순을 따르되 부모-자식 순서 유지 (확장)
  PATH <commit1> <commit2>          무방향 최단 경로 (없으면 No path)
  ANCESTORS <commit>                모든 조상 (가까운 순)
# 검색 (역색인)
  SEARCH <keyword>                  메시지 키워드 검색 (여러 단어는 AND)
  SEARCH --author=<name>            작성자 검색
# 보너스
  MERGE <branch_name>               부모가 2개인 merge commit 생성
  DIFF <file1> <file2>              두 텍스트 파일 줄 단위 비교
# 기타
  HELP                              도움말
  EXIT | QUIT                       종료
커밋 참조에는 전체 hash, 4자 이상 축약 hash, 브랜치 이름을 쓸 수 있습니다."""
