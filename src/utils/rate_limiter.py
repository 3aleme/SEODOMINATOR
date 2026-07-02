"""Token-bucket rate limiter for API calls."""

import functools
import time
import threading
from typing import Callable


class RateLimiter:
    """Token-bucket: allows up to `calls` per `period` seconds."""

    def __init__(self, calls: int, period: float):
        self._calls = calls
        self._period = period
        self._tokens = calls
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed >= self._period:
            self._tokens = self._calls
            self._last_refill = now

    def acquire(self) -> None:
        """Block until a token is available."""
        while True:
            with self._lock:
                self._refill()
                if self._tokens > 0:
                    self._tokens -= 1
                    return
            time.sleep(self._period / self._calls)

    def __call__(self, fn: Callable) -> Callable:
        """Decorator: rate-limit calls to wrapped function."""
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            self.acquire()
            return fn(*args, **kwargs)
        return wrapper
