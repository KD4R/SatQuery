"""
services/gateway/config.py — Gateway configuration from environment variables.
"""

import os
from typing import List


class GatewaySettings:
    """
    All Gateway settings resolved from environment variables.

    CORS_ALLOW_ORIGINS   Comma-separated list of allowed origins.
                         Defaults to a safe empty list (deny all cross-origin) in prod.
                         In local dev set to 'http://localhost:3000' etc.
    CORS_ALLOW_METHODS   Comma-separated HTTP methods. Default: GET,POST,PATCH,DELETE,OPTIONS
    RATE_LIMIT_REQUESTS  Max requests per window per client IP. Default: 100
    RATE_LIMIT_WINDOW_S  Window size in seconds. Default: 60
    """

    def __init__(self) -> None:
        raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
        self.cors_allow_origins: List[str] = (
            [o.strip() for o in raw_origins.split(",") if o.strip()] if raw_origins else []
        )
        raw_methods = os.getenv("CORS_ALLOW_METHODS", "GET,POST,PATCH,DELETE,OPTIONS,PUT")
        self.cors_allow_methods: List[str] = [
            m.strip() for m in raw_methods.split(",") if m.strip()
        ]
        self.cors_allow_headers: List[str] = [
            "Authorization",
            "Content-Type",
            "X-Trace-Id",
            "X-Request-Id",
        ]
        self.rate_limit_requests: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
        self.rate_limit_window_s: int = int(os.getenv("RATE_LIMIT_WINDOW_S", "60"))


_settings: GatewaySettings | None = None


def get_gateway_settings() -> GatewaySettings:
    global _settings
    if _settings is None:
        _settings = GatewaySettings()
    return _settings


def reset_gateway_settings() -> None:
    """Reset singleton — test use only."""
    global _settings
    _settings = None
