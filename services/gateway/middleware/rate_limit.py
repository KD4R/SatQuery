"""
services/gateway/middleware/rate_limit.py — Sliding-window rate limiter.

Implementation:
  - Client is identified by X-Forwarded-For or client.host.
  - Sliding window: tracks per-client request timestamps.
  - In-memory store — safe for single-process dev/test.
  - Production: swap _store for a Redis-backed adapter.

OWASP A04 Insecure Design mitigations:
  - 429 with Retry-After header — no silent dropping.
  - IP normalisation (IPv6 lowercased) prevents bypass via case variation.
  - Configurable limits via GatewaySettings.
"""

import time
from collections import defaultdict, deque
from typing import Deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter middleware.

    Client identity: by default the direct peer address is used. Client-supplied
    ``X-Forwarded-For`` is trusted ONLY when ``trust_proxy_headers=True`` is
    explicitly configured (i.e. the service is deployed behind a proxy that
    overwrites the header) — otherwise attackers could rotate spoofed IPs to
    bypass the limit and inflate the tracking store (A04/A05).
    """

    #: Hard cap on tracked clients so unique-IP floods cannot exhaust memory.
    _MAX_TRACKED_CLIENTS = 10_000

    def __init__(
        self,
        app,
        requests: int = 100,
        window_s: int = 60,
        trust_proxy_headers: bool = False,
    ) -> None:
        super().__init__(app)
        self._max_requests = requests
        self._window_s = window_s
        self._trust_proxy_headers = trust_proxy_headers
        self._store: dict[str, Deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        if self._trust_proxy_headers:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                # Take the leftmost (original client) IP
                ip = forwarded.split(",")[0].strip()
            else:
                ip = request.client.host if request.client else "unknown"
        else:
            # Never trust client-supplied headers: use the direct peer.
            ip = request.client.host if request.client else "unknown"
        return ip.lower()

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks to avoid false alarms in monitoring
        if request.url.path.endswith("/health"):
            return await call_next(request)

        key = self._client_key(request)
        now = time.monotonic()
        window_start = now - self._window_s

        # Bound the store: if a flood of unique clients fills it, drop the
        # oldest tracking bucket. Worst case a dropped client gets a fresh
        # window — acceptable vs. unbounded memory growth (A04 DoS).
        if len(self._store) > self._MAX_TRACKED_CLIENTS and key not in self._store:
            oldest = next(iter(self._store))
            del self._store[oldest]

        timestamps = self._store[key]

        # Evict expired entries
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        if len(timestamps) >= self._max_requests:
            retry_after = int(self._window_s - (now - timestamps[0]))
            return JSONResponse(
                status_code=429,
                content={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": (
                        f"Rate limit exceeded. "
                        f"Max {self._max_requests} requests per {self._window_s}s."
                    ),
                    "retryable": True,
                },
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        timestamps.append(now)
        return await call_next(request)
