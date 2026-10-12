"""과제 제약 자동 검증: 정렬 표준 API·그래프 라이브러리 미사용, docstring 작성."""

import ast
import pathlib
import unittest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "mini_git"
BANNED_CALLS = {"sorted"}
BANNED_METHODS = {"sort"}
BANNED_MODULES = {"heapq", "bisect", "graphlib", "networkx", "igraph", "graph_tool", "rustworkx"}


def sources():
    for path in sorted(PACKAGE.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"))


class BannedApiTest(unittest.TestCase):
    def test_no_standard_sort_or_graph_libraries(self):
        violations = []
        for path, tree in sources():
            rel = path.relative_to(PACKAGE.parent)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
                        violations.append("{}:{} sorted()".format(rel, node.lineno))
                    if isinstance(node.func, ast.Attribute) and node.func.attr in BANNED_METHODS:
                        violations.append("{}:{} .sort()".format(rel, node.lineno))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in BANNED_MODULES:
                            violations.append("{}:{} import {}".format(rel, node.lineno, alias.name))
                elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in BANNED_MODULES:
                    violations.append("{}:{} from {} import".format(rel, node.lineno, node.module))
        self.assertEqual(violations, [], "\n".join(violations))


class SeparationTest(unittest.TestCase):
    def test_algorithms_live_in_their_own_modules(self):
        for name in ("graph.py", "sorting.py", "index.py"):
            self.assertTrue((PACKAGE / name).is_file(), name)

    def test_public_api_has_docstrings(self):
        missing = []
        for path, tree in sources():
            rel = path.relative_to(PACKAGE.parent)
            if ast.get_docstring(tree) is None:
                missing.append(str(rel))
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    if ast.get_docstring(node) is None:
                        missing.append("{}:{}".format(rel, node.name))
                if isinstance(node, ast.ClassDef) and not issubclass_exception(node):
                    if ast.get_docstring(node) is None:
                        missing.append("{}:{}".format(rel, node.name))
        self.assertEqual(missing, [], "\n".join(missing))


def issubclass_exception(node: ast.ClassDef) -> bool:
    """에러 클래스(이름이 곧 설명)는 docstring 검사에서 제외."""
    return any(isinstance(b, ast.Name) and (b.id.endswith("Error") or b.id.endswith("Exception")
                                            or b.id in ("InvalidArgs", "MiniGitError")) for b in node.bases)


if __name__ == "__main__":
    unittest.main()
