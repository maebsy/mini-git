"""시간 공급자.

커밋 timestamp 를 ``datetime.now()`` 에서 직접 얻지 않고 시계 객체로 주입받는다.

* ``SystemClock``  : 실제 현재 시각 (기본값)
* ``SteppingClock``: 시작 시각에서 호출할 때마다 일정 간격씩 증가하는 가짜 시계
  → ``--fake-time "2024-01-15 09:00:00" --time-step 900`` 으로 README 예시와 같은 시각을 재현하고,
    테스트에서 날짜 정렬 결과를 항상 같게 만든다.
"""

from datetime import datetime, timedelta


class SystemClock:
    """실제 현재 시각을 반환한다."""

    def now(self) -> datetime:
        return datetime.now()


class SteppingClock:
    """``now()`` 를 부를 때마다 ``step_seconds`` 만큼 앞으로 가는 시계."""

    def __init__(self, start: datetime, step_seconds: float = 60.0) -> None:
        self._next = start
        self._step = timedelta(seconds=step_seconds)

    def now(self) -> datetime:
        current = self._next
        self._next = current + self._step
        return current
