"""[보너스] 줄 단위 텍스트 비교 (LCS 기반).

두 파일의 **최장 공통 부분 수열(LCS)** 을 동적 계획법으로 구한 뒤,
LCS 에 속한 줄은 공통(" "), 첫 파일에만 있는 줄은 삭제("-"), 두 번째 파일에만 있는 줄은 추가("+")로 표시한다.

    dp[i][j] = a[i:] 와 b[j:] 의 LCS 길이
             = dp[i+1][j+1] + 1               (a[i] == b[j])
             = max(dp[i+1][j], dp[i][j+1])    (그 외)

시간·공간 O(n × m). 실제 Git 은 O((n+m)·D) 인 Myers 알고리즘을 쓰지만,
학습 목적상 원리가 가장 잘 드러나는 LCS 방식을 택했다.
"""

from typing import List, Tuple

COMMON, REMOVED, ADDED = " ", "-", "+"


def diff_lines(a: List[str], b: List[str]) -> List[Tuple[str, str]]:
    """(태그, 줄) 목록을 반환한다. 태그는 ' ', '-', '+' 중 하나."""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        row, below = dp[i], dp[i + 1]
        for j in range(m - 1, -1, -1):
            if a[i] == b[j]:
                row[j] = below[j + 1] + 1
            else:
                row[j] = below[j] if below[j] >= row[j + 1] else row[j + 1]

    result: List[Tuple[str, str]] = []
    i = j = 0
    while i < n and j < m:
        if a[i] == b[j]:
            result.append((COMMON, a[i]))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            result.append((REMOVED, a[i]))  # 삭제를 먼저 보여준다(Git 과 같은 관례)
            i += 1
        else:
            result.append((ADDED, b[j]))
            j += 1
    result.extend((REMOVED, line) for line in a[i:])
    result.extend((ADDED, line) for line in b[j:])
    return result


def read_lines(path: str) -> List[str]:
    """UTF-8 텍스트 파일을 줄 목록으로 읽는다(줄바꿈 문자 제외)."""
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def render_diff(path_a: str, path_b: str, entries: List[Tuple[str, str]]) -> List[str]:
    """diff 결과를 ``--- a`` / ``+++ b`` 헤더와 요약 줄을 포함한 출력 형식으로 만든다."""
    lines = ["--- {}".format(path_a), "+++ {}".format(path_b)]
    lines.extend("{} {}".format(tag, text) for tag, text in entries)
    common = sum(1 for tag, _ in entries if tag == COMMON)
    removed = sum(1 for tag, _ in entries if tag == REMOVED)
    added = sum(1 for tag, _ in entries if tag == ADDED)
    lines.append("Summary: {} common, {} removed, {} added".format(common, removed, added))
    return lines
