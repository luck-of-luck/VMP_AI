"""Token-bucket rate limiting for HTTP transports.

A per-client token bucket: each client (identified by bearer token or IP) gets
``rate_limit_per_min`` tokens that refill continuously. A request consumes one
token; when the bucket is empty the request is rejected. Disabled entirely when
``rate_limit_per_min == 0`` (the default) or for stdio (no client identity).

This is intentionally in-process and best-effort — appropriate for a single
server instance. Horizontally-scaled deployments should put a real rate limiter
(e.g. an API gateway) in front.
"""

import threading
import time
from dataclasses import dataclass

from sast_mcp_server.config import get_settings


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class RateLimiter:
    """In-process per-client token-bucket limiter."""

    def __init__(self, per_minute: int | None = None) -> None:
        if per_minute is None:
            per_minute = get_settings().rate_limit_per_min
        self.per_minute = max(0, per_minute)
        self._capacity = float(self.per_minute)
        self._refill_per_sec = self.per_minute / 60.0
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.per_minute > 0

    def check(self, client_id: str) -> bool:
        """Consume one token for ``client_id``; return False if exhausted."""
        if not self.enabled:
            return True

        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(client_id)
            if bucket is None:
                # First request: full bucket minus this one.
                self._buckets[client_id] = _Bucket(
                    tokens=self._capacity - 1.0, last_refill=now
                )
                return True

            elapsed = now - bucket.last_refill
            bucket.tokens = min(
                self._capacity, bucket.tokens + elapsed * self._refill_per_sec
            )
            bucket.last_refill = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True
            return False

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()
