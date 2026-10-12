import io
import os
import tempfile
import unittest

from mini_git.cli import tokenize
from mini_git.repl import build_runner, run
from tests.helpers import make_runner


def run_lines(runner, *lines):
    out = []
    for line in lines:
        out.extend(runner.execute(line))
    return out


class TokenizeTest(unittest.TestCase):
    def test_quotes_and_windows_paths(self):
        self.assertEqual(tokenize('COMMIT "Add login feature"'), ["COMMIT", "Add login feature"])
        self.assertEqual(tokenize("commit 'it is'"), ["commit", "it is"])
        self.assertEqual(tokenize('SEARCH --author="Alice Kim"'), ["SEARCH", "--author=Alice Kim"])
        self.assertEqual(tokenize(r'DIFF "C:\dev\a.txt" b.txt'), ["DIFF", r"C:\dev\a.txt", "b.txt"])
        self.assertEqual(tokenize(r'commit "say \"hi\""'), ["commit", 'say "hi"'])
        self.assertEqual(tokenize('commit ""'), ["commit", ""])


class MissionExampleTest(unittest.TestCase):
    def test_example_flow(self):
        r = make_runner(mode="sha1")
        self.assertEqual(r.execute('init "Alice"'),
                         ["Initialized repository.", "Current branch: main", "Current user: Alice"])
        root = r.execute('commit "Initial commit"')[0]
        self.assertRegex(root, r"^\[main [0-9a-f]{7}\] Initial commit$")
        self.assertEqual(r.execute("branch feature"), ["Created branch: feature"])
        self.assertEqual(r.execute("switch feature"), ["Switched to branch: feature"])
        self.assertRegex(r.execute('commit "Add login feature"')[0], r"^\[feature [0-9a-f]{7}\] Add login feature$")
        r.execute("switch main")
        r.execute('commit "Add payment feature"')
        log = r.execute("log")
        self.assertEqual([line for line in log if not line.startswith("commit")],
                         ["Initial commit", "Add login feature", "Add payment feature"])
        self.assertIn("(Alice, 2024-01-15 09:00:00) [main]", log[0])
        self.assertIn("(Alice, 2024-01-15 09:15:00) [feature]", log[2])
        self.assertIn("(HEAD -> main)", log[4])
        h = {c.message: c.hash for c in r.repo.commits.values()}
        self.assertEqual(r.execute("path {} {}".format(h["Initial commit"], h["Add payment feature"]))[0],
                         "Path: {} -> {}".format(h["Initial commit"], h["Add payment feature"]))
        self.assertEqual(r.execute('search "login"'),
                         ["Found 1 commit:", "- {}: Add login feature (Alice, 2024-01-15 09:15:00)".format(h["Add login feature"])])


class CommandBehaviourTest(unittest.TestCase):
    def setUp(self):
        self.r = make_runner()
        run_lines(self.r, "init Alice", 'commit "Initial commit"', "branch feature", "switch feature",
                  'commit "Add login feature"', "switch main", 'commit "Add payment feature"')
        # counter 모드 hash: 0000001(Initial), 0000002(login), 0000003(payment)

    def test_case_insensitive_commands(self):
        self.assertEqual(self.r.execute("SWITCH feature"), ["Switched to branch: feature"])
        self.assertEqual(self.r.execute("sWiTcH main"), ["Switched to branch: main"])

    def test_standard_errors(self):
        self.assertEqual(self.r.execute("switch nope"), ["Unknown branch: nope"])
        self.assertEqual(self.r.execute("ancestors deadbeef"), ["Unknown commit: deadbeef"])
        self.assertEqual(self.r.execute("path 0000001"), ["Invalid args"])
        self.assertEqual(self.r.execute("commit"), ["Invalid args"])
        self.assertEqual(self.r.execute("log --sort-by=size"), ["Invalid args: --sort-by must be date or author"])
        self.assertEqual(self.r.execute("search --author="), ["Invalid args"])
        self.assertEqual(self.r.execute('commit "unclosed'), ["Invalid args: unbalanced quotes"])
        self.assertTrue(self.r.execute("frobnicate")[0].startswith("Unknown command"))

    def test_not_initialized(self):
        r = make_runner()
        self.assertEqual(r.execute("commit x"), ["Not initialized. Run: INIT <user_name>"])

    def test_path_and_no_path(self):
        self.assertEqual(self.r.execute("path 0000002 0000003"),
                         ["Path: 0000002 -> 0000001 -> 0000003", "(2 edges)"])
        run_lines(self.r, "switch --orphan docs", 'commit "docs root"')
        self.assertEqual(self.r.execute("path 0000001 0000004"), ["No path"])

    def test_ancestors(self):
        out = self.r.execute("ancestors 0000003")
        self.assertEqual(out[0], "Ancestors of 0000003 (1):")
        self.assertTrue(out[1].startswith("- 0000001 [distance 1]"))
        self.assertEqual(self.r.execute("ancestors 0000001"), ["Ancestors of 0000001: none (root commit)"])
        self.assertEqual(self.r.execute("ancestors feature")[0], "Ancestors of 0000002 (1):")

    def test_search_author_and_keyword(self):
        run_lines(self.r, "user Bob", 'commit "Fix login bug"')
        self.assertEqual(self.r.execute("search --author=Bob")[0], "Found 1 commit:")
        self.assertEqual(self.r.execute("search login")[0], "Found 2 commits:")
        self.assertEqual(self.r.execute("search Login Bug")[0], "Found 1 commit:")
        self.assertEqual(self.r.execute("search nothing"), ["Found 0 commits."])

    def test_log_sort_options(self):
        run_lines(self.r, "user Aaron", 'commit "later by Aaron"')
        by_author = [l for l in self.r.execute("log --sort-by=author") if l.startswith("commit")]
        self.assertIn("Aaron", by_author[0])
        by_date = [l for l in self.r.execute("log --sort-by=date --algo=quick") if l.startswith("commit")]
        self.assertIn("09:00:00", by_date[0])
        topo = [l for l in self.r.execute("log --sort-by=author --topo") if l.startswith("commit")]
        self.assertIn("0000001", topo[0])  # 루트는 작성자와 무관하게 맨 앞
        self.assertEqual(self.r.execute("log --algo=quick"), ["Invalid args: --topo/--algo need --sort-by"])

    def test_branch_list(self):
        self.assertEqual(self.r.execute("branch"),
                         ["  feature      0000002 Add login feature", "* main         0000003 Add payment feature"])

    def test_merge_command(self):
        out = self.r.execute("merge feature")
        self.assertEqual(out[0], "[main 0000004] Merge branch 'feature' into main")
        self.assertEqual(out[1], "Parents: 0000003 (HEAD), 0000002 (feature)")
        self.assertIn("Merge: 0000003 0000002", self.r.execute("log"))
        self.assertEqual(self.r.execute("merge feature"), ["Already up to date."])

    def test_diff_command(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "a.txt"), os.path.join(d, "b.txt")
            with open(a, "w", encoding="utf-8") as f:
                f.write("one\ntwo\nthree\n")
            with open(b, "w", encoding="utf-8") as f:
                f.write("one\nTWO\nthree\nfour\n")
            out = self.r.execute('diff "{}" "{}"'.format(a, b))
            self.assertEqual(out[2:], ["  one", "- two", "+ TWO", "  three", "+ four",
                                       "Summary: 2 common, 1 removed, 2 added"])
            self.assertTrue(self.r.execute("diff {} nope.txt".format(a))[0].startswith("File not found"))


class ReplTest(unittest.TestCase):
    def test_piped_transcript_and_exit(self):
        runner = build_runner(["--hash-mode", "counter", "--fake-time", "2024-01-15 09:00:00", "--time-step", "900"])
        stdin = io.StringIO("# demo\ninit Alice\ncommit hello\nquit\ncommit ignored\n")
        stdout = io.StringIO()
        self.assertEqual(run(runner, stdin=stdin, stdout=stdout, interactive=False), 0)
        self.assertEqual(stdout.getvalue().splitlines(), [
            "mini-git> # demo",
            "mini-git> init Alice",
            "Initialized repository.",
            "Current branch: main",
            "Current user: Alice",
            "mini-git> commit hello",
            "[main 0000001] hello",
            "mini-git> quit",
        ])


if __name__ == "__main__":
    unittest.main()
