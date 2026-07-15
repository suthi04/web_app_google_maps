"""In-process guards for expensive anonymous analysis requests."""

import math
import threading
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    """Thread-safe per-key rate limiter; ``max_requests=0`` disables it."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._events = defaultdict(deque)
        self._lock = threading.Lock()

    def consume(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """Consume one slot and return ``(allowed, retry_after_seconds)``."""
        if self.max_requests <= 0:
            return True, 0

        now = time.monotonic() if now is None else now
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= self.max_requests:
                retry_after = max(1, math.ceil(self.window_seconds - (now - events[0])))
                return False, retry_after

            events.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


class ConcurrencyGate:
    """Bound the number of expensive jobs running inside this process."""

    def __init__(self, limit: int):
        self.limit = max(1, limit)
        self._semaphore = threading.BoundedSemaphore(self.limit)
        self._active = 0
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        acquired = self._semaphore.acquire(blocking=False)
        if acquired:
            with self._lock:
                self._active += 1
        return acquired

    def release(self) -> None:
        self._semaphore.release()
        with self._lock:
            self._active -= 1

    def snapshot(self) -> dict:
        """Return a consistent, read-only capacity snapshot for observability."""
        with self._lock:
            active = self._active
        return {
            "capacity": self.limit,
            "inflight": active,
            "available": self.limit - active,
        }
