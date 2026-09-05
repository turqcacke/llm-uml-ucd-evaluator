import asyncio
import time
from collections import deque
from typing import Protocol


class BaseRateLimiter(Protocol):
    async def acquire(self) -> None: ...


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, period: float) -> None:
        if max_requests <= 0 or period <= 0:
            raise ValueError("max_requests and period must be positive")
        self._timestamps: deque[float] = deque()
        self._max_requests = max_requests
        self._period = period
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                while (
                    self._timestamps
                    and self._timestamps[0] + self._period <= now
                ):
                    self._timestamps.popleft()

                if len(self._timestamps) < self._max_requests:
                    self._timestamps.append(now)
                    return

                delay = self._timestamps[0] + self._period - now
            await asyncio.sleep(delay)
