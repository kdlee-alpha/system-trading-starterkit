"""Kiwoom TR 요청 속도 제한기 (deque 기반 슬라이딩 윈도우)"""

import asyncio
import time
from collections import deque


class KiwoomRateLimiter:
    """
    슬라이딩 윈도우 방식의 TR 요청 속도 제한기

    Kiwoom API는 초당 최대 5회 TR 요청 가능.
    한도 초과 시 asyncio.sleep으로 자동 대기.
    """

    def __init__(self, max_calls: int = 5, period: float = 1.0) -> None:
        """
        Args:
            max_calls: 허용 최대 요청 수
            period: 측정 기간 (초)
        """
        self.max_calls = max_calls
        self.period = period
        self._call_times: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        요청 슬롯 획득 - 한도 초과 시 자동 대기

        모든 API 요청 전에 호출해야 합니다.
        """
        async with self._lock:
            now = time.monotonic()
            window_start = now - self.period

            # 윈도우 밖의 오래된 요청 시간 제거
            while self._call_times and self._call_times[0] <= window_start:
                self._call_times.popleft()

            # 한도 초과 시 대기
            if len(self._call_times) >= self.max_calls:
                oldest = self._call_times[0]
                wait_time = oldest + self.period - now
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    # 대기 후 오래된 요청 재정리
                    now = time.monotonic()
                    window_start = now - self.period
                    while self._call_times and self._call_times[0] <= window_start:
                        self._call_times.popleft()

            # 현재 요청 시간 기록
            self._call_times.append(time.monotonic())

    @property
    def remaining_calls(self) -> int:
        """현재 윈도우에서 남은 요청 가능 횟수"""
        now = time.monotonic()
        window_start = now - self.period
        current_calls = sum(1 for t in self._call_times if t > window_start)
        return max(0, self.max_calls - current_calls)
