"""
services/gateway/middleware/security_headers.py — Security response headers.

OWASP A05 (Security Misconfiguration) / Secure Headers Project:
  - X-Content-Type-Options: nosniff   — prevents MIME-type sniffing attacks.
  - X-Frame-Options: DENY             — prevents clickjacking on error/health pages.
  - Referrer-Policy: no-referrer      — never leak URLs (may contain mission ids) cross-origin.
  - Content-Security-Policy: default-src 'none' — this is a JSON API, not a page;
    any injected markup must not execute when rendered in a browser.
  - Cache-Control: no-store on non-GET — mission/job responses are tenant-private;
    they must never be cached by shared intermediaries.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        for name, value in _SECURITY_HEADERS.items():
            if name not in response.headers:
                response.headers[name] = value
        if request.method not in ("GET", "HEAD") and "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response
