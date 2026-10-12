"""커밋 hash 생성 전략.

세 가지 방식을 제공하고, 모두 **세션 내 유일성**을 같은 방법으로 보장한다.

=========  ==========================================  ==================================
모드        생성 방식                                    특징
=========  ==========================================  ==================================
sha1       커밋 내용(순번·작성자·시각·메시지·부모)의        실제 Git 처럼 내용 기반(content-addressed).
(기본값)    SHA-1 앞 7자리                                같은 입력이면 같은 hash → 재현 가능
counter    순번을 16진수 7자리로 (0000001, 0000002 …)      가장 예측 가능. 디버깅·테스트에 유리.
                                                         사전순 = 생성순
random     난수 28비트 → 16진수 7자리                      실제 Git 처럼 예측 불가.
                                                         ``--seed`` 를 주면 재현 가능
=========  ==========================================  ==================================

유일성 보장: 후보 hash 가 이미 존재하면(충돌) 길이를 한 글자씩 늘리고, 40자를 다 써도
충돌하면 순번을 덧붙여 다시 계산한다. 생성 결과는 항상 저장소 조회로 검증한다.
"""

import hashlib
import random
from typing import Callable, Optional

SHORT_LEN = 7
HASH_MODES = ("sha1", "counter", "random")


class HashGenerator:
    """커밋 hash 생성기. ``exists`` 콜백으로 중복 여부를 확인한다."""

    def __init__(self, mode: str = "sha1", seed: Optional[int] = None) -> None:
        if mode not in HASH_MODES:
            raise ValueError("unknown hash mode: {}".format(mode))
        self.mode = mode
        self._rng = random.Random(seed)
        self.collisions = 0

    def generate(self, payload: str, seq: int, exists: Callable[[str], bool]) -> str:
        """``payload`` (커밋 내용 문자열)과 순번으로 유일한 hash 를 만든다."""
        if self.mode == "counter":
            candidate = "{:07x}".format(seq + 1)  # 순번은 유일하므로 충돌하지 않는다
            if not exists(candidate):
                return candidate
            self.collisions += 1
            return self._extend(hashlib.sha1(payload.encode("utf-8")).hexdigest(), exists, seq)
        if self.mode == "random":
            for _ in range(1000):
                candidate = "{:07x}".format(self._rng.getrandbits(28))
                if not exists(candidate):
                    return candidate
                self.collisions += 1
            return self._extend("{:040x}".format(self._rng.getrandbits(160)), exists, seq)
        full = hashlib.sha1(payload.encode("utf-8")).hexdigest()
        return self._extend(full, exists, seq)

    def _extend(self, full: str, exists: Callable[[str], bool], seq: int) -> str:
        """앞 7자리가 충돌하면 한 글자씩 늘린다(Git 의 abbreviated hash 와 같은 아이디어)."""
        for length in range(SHORT_LEN, len(full) + 1):
            candidate = full[:length]
            if not exists(candidate):
                return candidate
            self.collisions += 1
        salted = hashlib.sha1("{}:{}".format(full, seq).encode("utf-8")).hexdigest()
        return self._extend(salted, exists, seq + 1)
