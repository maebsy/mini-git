"""[보너스] 정렬 알고리즘 성능 비교.

직접 구현한 4개 알고리즘(merge, quick, heap, insertion)을 입력 크기와 입력 형태별로 측정한다.

    python scripts/benchmark_sort.py                  # 기본 크기 100, 1,000, 5,000, 20,000
    python scripts/benchmark_sort.py 100 1000 50000   # 크기 지정

입력 형태
* random      : 무작위 정수
* sorted      : 이미 정렬됨 (커밋 timestamp 처럼 대부분 시간순으로 쌓이는 데이터)
* reversed    : 역순 (최악 사례 확인)
* few-unique  : 값 종류가 5개뿐 (작성자 기준 정렬처럼 동률이 많은 데이터)

각 측정은 3회 반복 후 최솟값(ms). 삽입 정렬은 O(n²) 이라 n > 5,000 의 random/reversed/few-unique 는 생략.
마지막에 안정성 실험(같은 키의 원래 순서 유지 여부)도 출력한다.
"""

import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mini_git.sorting import ALGORITHM_INFO, ALGORITHMS  # noqa: E402

REPEAT = 3
INSERTION_LIMIT = 5_000


def make_inputs(n: int, rng: random.Random):
    return {
        "random": [rng.randint(0, n * 10) for _ in range(n)],
        "sorted": list(range(n)),
        "reversed": list(range(n, 0, -1)),
        "few-unique": [rng.randint(0, 4) for _ in range(n)],
    }


def measure(func, data) -> float:
    best = float("inf")
    for _ in range(REPEAT):
        t0 = time.perf_counter()
        func(data)
        best = min(best, time.perf_counter() - t0)
    return best * 1000


def stability_demo() -> None:
    rng = random.Random(0)
    items = [(rng.randint(0, 2), i) for i in range(40)]  # (작성자 번호, 원래 순서)
    print("\n## 안정성 실험 (키가 같은 원소의 원래 순서가 유지되는가)\n")
    print("| 알고리즘 | 유지됨 | 순서가 뒤집힌 인접 쌍 수 |")
    print("|---|---|---|")
    for name, func in ALGORITHMS.items():
        out = func(items, key=lambda x: x[0])
        broken = sum(1 for a, b in zip(out, out[1:]) if a[0] == b[0] and a[1] > b[1])
        print("| {} | {} | {} |".format(name, "✅" if broken == 0 else "❌", broken))


def main() -> None:
    sizes = [int(a) for a in sys.argv[1:]] or [100, 1_000, 5_000, 20_000]
    rng = random.Random(42)
    print("## 이론적 특성\n")
    print("| 알고리즘 | 평균 | 최악 | 추가 공간 | 안정 |")
    print("|---|---|---|---|---|")
    for name, (avg, worst, space, stable) in ALGORITHM_INFO.items():
        print("| {} | {} | {} | {} | {} |".format(name, avg, worst, space, "✅" if stable else "❌"))

    print("\n## 실행 시간 (ms, {}회 중 최솟값)\n".format(REPEAT))
    names = list(ALGORITHMS)
    print("| N | 입력 | " + " | ".join(names) + " |")
    print("|---|---|" + "---|" * len(names))
    for n in sizes:
        for kind, data in make_inputs(n, rng).items():
            row = []
            for name in names:
                if name == "insertion" and n > INSERTION_LIMIT and kind != "sorted":
                    row.append("—")
                else:
                    row.append("{:.2f}".format(measure(ALGORITHMS[name], data)))
            print("| {:,} | {} | {} |".format(n, kind, " | ".join(row)))
    stability_demo()
    print("\nPython {} / {}".format(sys.version.split()[0], sys.platform))


if __name__ == "__main__":
    main()
