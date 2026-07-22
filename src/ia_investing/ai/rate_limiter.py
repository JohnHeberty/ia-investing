from __future__ import annotations

import time
from collections import deque


class TokenBucketRateLimiter:
    def __init__(self, rpm: int, tpm: int, window_seconds: float = 60.0) -> None:
        if rpm < 1:
            raise ValueError("rpm must be at least 1")
        if tpm < 1:
            raise ValueError("tpm must be at least 1")
        self.max_rpm = rpm
        self.max_tpm = tpm
        self.window = window_seconds
        self._requests: deque[tuple[float, int]] = deque()
        self._lock = __import__("asyncio").Lock()

    async def acquire(self, estimated_tokens: int = 0) -> float:
        async with self._lock:
            self._evict()
            rpm_used = len(self._requests)
            tpm_used = sum(t for _, t in self._requests)
            if rpm_used < self.max_rpm and (tpm_used + estimated_tokens) <= self.max_tpm:
                self._requests.append((time.monotonic(), estimated_tokens))
                return 0.0
            if self._requests:
                return (self._requests[0][0] + self.window) - time.monotonic()
            return 0.0

    def _evict(self) -> None:
        cutoff = time.monotonic() - self.window
        while self._requests and self._requests[0][0] < cutoff:
            self._requests.popleft()

    @property
    def rpm_used(self) -> int:
        self._evict()
        return len(self._requests)

    @property
    def tpm_used(self) -> int:
        self._evict()
        return sum(t for _, t in self._requests)
