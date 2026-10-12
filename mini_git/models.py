"""도메인 모델: 커밋 노드."""

from dataclasses import dataclass
from datetime import datetime
from typing import Tuple

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class Commit:
    """커밋 그래프의 노드.

    과제 최소 필드(hash, message, author, timestamp, parents) 외에 두 필드를 더 둔다.

    * ``seq``    : 생성 순번(0, 1, 2 …). 같은 초에 만든 커밋의 순서를 결정하는 동률 처리 기준이다.
    * ``branch`` : 커밋을 만들 때의 브랜치 이름. LOG 출력에서 ``[main]`` 처럼 표시한다.

    ``frozen=True`` 로 불변 객체로 만든다. 커밋은 한 번 만들어지면 바뀌지 않아야
    해시와 내용이 어긋나지 않고, 그래프 탐색 중에도 안전하다.
    """

    hash: str
    message: str
    author: str
    timestamp: datetime
    parents: Tuple[str, ...]
    seq: int
    branch: str

    @property
    def is_merge(self) -> bool:
        return len(self.parents) >= 2

    @property
    def is_root(self) -> bool:
        return len(self.parents) == 0

    def time_str(self) -> str:
        return self.timestamp.strftime(TIMESTAMP_FORMAT)
