import unittest

from mini_git.index import InvertedIndex, tokenize


class TokenizeTest(unittest.TestCase):
    def test_split_lower_strip_punct_dedupe(self):
        self.assertEqual(tokenize("Add Login, login feature!"), ["add", "login", "feature"])
        self.assertEqual(tokenize("  "), [])
        self.assertEqual(tokenize("로그인 기능 추가"), ["로그인", "기능", "추가"])


class InvertedIndexTest(unittest.TestCase):
    def setUp(self):
        self.idx = InvertedIndex()
        self.idx.add("c1", "Initial commit", "Alice")
        self.idx.add("c2", "Add login feature", "Alice")
        self.idx.add("c3", "Fix login bug", "Bob Kim")
        self.idx.add("c4", "Add payment feature", "bob kim")

    def test_keyword_lookup_preserves_creation_order(self):
        self.assertEqual(self.idx.search_keyword("login"), ["c2", "c3"])
        self.assertEqual(self.idx.search_keyword("LOGIN"), ["c2", "c3"])
        self.assertEqual(self.idx.search_keyword("nothing"), [])

    def test_multi_word_is_and(self):
        self.assertEqual(self.idx.search_keyword("add feature"), ["c2", "c4"])
        self.assertEqual(self.idx.search_keyword("login feature"), ["c2"])
        self.assertEqual(self.idx.search_keyword("login payment"), [])

    def test_author_index_normalized(self):
        self.assertEqual(self.idx.search_author("alice"), ["c1", "c2"])
        self.assertEqual(self.idx.search_author("Bob  Kim"), ["c3", "c4"])
        self.assertEqual(self.idx.search_author("carol"), [])

    def test_stats(self):
        self.assertEqual(self.idx.stats()["authors"], 2)


if __name__ == "__main__":
    unittest.main()
