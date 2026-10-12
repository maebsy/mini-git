"""역색인 (Inverted Index).

커밋이 만들어질 때마다 "단어 → 커밋 목록", "작성자 → 커밋 목록"을 미리 갱신해 둔다.
SEARCH 는 전체 커밋을 훑지 않고 색인에서 후보 목록을 바로 꺼낸다.

==================  ==============================  ===============================
                     순회 검색                        역색인 검색
==================  ==============================  ===============================
SEARCH 비용          O(N × 메시지 길이) — 매번 전체 순회   O(1) 조회 + O(k) 결과 출력
COMMIT 비용          O(1)                             O(메시지 토큰 수) — 색인 갱신
메모리               추가 없음                          토큰 수만큼 posting 추가
==================  ==============================  ===============================

N 은 전체 커밋 수, k 는 결과 개수. 검색이 커밋보다 훨씬 자주 일어나는 환경에서 유리하다.

키워드 추출 기준 (과제 최소 기준 + 정규화 1단계 추가)
1. 메시지를 공백으로 split
2. 소문자(lower)로 정규화
3. (추가) 토큰 앞뒤의 문장부호 제거 → ``"login,"`` 과 ``"login"`` 을 같은 단어로 취급
"""

import string
from typing import Dict, Iterable, List

_PUNCT = string.punctuation + "“”‘’…·"


def tokenize(message: str) -> List[str]:
    """메시지에서 색인용 키워드를 추출한다. 같은 메시지 안의 중복 단어는 한 번만."""
    seen = set()
    tokens: List[str] = []
    for raw in message.split():
        token = raw.lower().strip(_PUNCT)
        if token and token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def normalize_author(name: str) -> str:
    """작성자 색인 키: 대소문자·앞뒤 공백 무시 ('Alice' == 'alice')."""
    return " ".join(name.split()).casefold()


class InvertedIndex:
    """keyword → [commit hash], author → [commit hash] 두 종류의 색인."""

    def __init__(self) -> None:
        self._by_keyword: Dict[str, List[str]] = {}
        self._by_author: Dict[str, List[str]] = {}

    def add(self, commit_hash: str, message: str, author: str) -> None:
        """커밋 생성 시점에 호출된다. posting 목록 끝에 추가하므로 항상 생성 순서를 유지한다."""
        for token in tokenize(message):
            self._by_keyword.setdefault(token, []).append(commit_hash)
        self._by_author.setdefault(normalize_author(author), []).append(commit_hash)

    def search_keyword(self, query: str) -> List[str]:
        """키워드 검색. 여러 단어면 모든 단어를 포함한 커밋(AND)만 반환한다.

        가장 짧은 posting 목록을 기준으로 나머지 목록에 있는지 확인한다(교집합).
        결과는 커밋 생성 순서다.
        """
        terms = tokenize(query)
        if not terms:
            return []
        postings = [self._by_keyword.get(t, []) for t in terms]
        if any(not p for p in postings):
            return []
        shortest = min(postings, key=len)
        others = [set(p) for p in postings if p is not shortest]
        return [h for h in shortest if all(h in o for o in others)]

    def search_author(self, name: str) -> List[str]:
        return list(self._by_author.get(normalize_author(name), []))

    def keywords(self) -> Iterable[str]:
        return self._by_keyword.keys()

    def stats(self) -> Dict[str, int]:
        return {
            "keywords": len(self._by_keyword),
            "authors": len(self._by_author),
            "postings": sum(len(v) for v in self._by_keyword.values()),
        }
