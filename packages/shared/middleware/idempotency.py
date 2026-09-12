"""
packages/shared/middleware/idempotency.py — Idempotency Control (P1-12).

Intercepts POST and PATCH requests containing an `Idempotency-Key` header.
Caches the response so that duplicate requests return the same result instead
of re-executing state-mutating operations.
"""

import hashlib
import json
import logging
from typing import Dict, Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# In-memory store: key -> {"status": "in-progress" | "done", "response": dict, "status_code": int}
# In production, this must be a distributed cache like Redis with TTL.
_IDEMPOTENCY_STORE: Dict[str, Dict[str, Any]] = {}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in ("POST", "PATCH"):
            return await call_next(request)

        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return await call_next(request)

        # To prevent key collision across tenants/users, mix the key with the authorization token
        auth_header = request.headers.get("Authorization", "")
        store_key = hashlib.sha256(f"{idem_key}:{auth_header}".encode()).hexdigest()

        if store_key in _IDEMPOTENCY_STORE:
            state = _IDEMPOTENCY_STORE[store_key]
            if state["status"] == "in-progress":
                logger.warning("Concurrent duplicate request for idempotency key: %s", idem_key)
                return JSONResponse(
                    status_code=409,
                    content={
                        "code": "CONCURRENT_REQUEST",
                        "message": "A request with this Idempotency-Key "
                        "is currently being processed.",
                        "retryable": True,
                    },
                )
            elif state["status"] == "done":
                logger.info("Idempotent cache hit for key: %s", idem_key)
                return JSONResponse(
                    status_code=state["status_code"],
                    content=state["response"],
                )

        # Mark as in-progress
        _IDEMPOTENCY_STORE[store_key] = {"status": "in-progress"}

        try:
            response = await call_next(request)
        except Exception:
            # If the handler fails unhandled, clear the lock so it can be retried
            _IDEMPOTENCY_STORE.pop(store_key, None)
            raise

        # We can only cache JSON responses. If it's a streaming/binary response, skip.
        # But wait, to read the response body in Starlette middleware without consuming it forever,
        # we have to iterate it. Since we enforce JSON everywhere, we can just intercept
        # JSONResponses. But `call_next` returns a StreamingResponse.

        body = b""
        if hasattr(response, "body_iterator"):
            async for chunk in getattr(response, "body_iterator"):  # type: ignore[union-attr]
                if isinstance(chunk, bytes):
                    body += chunk
                else:
                    body += chunk.encode()

        # Reconstruct the response
        new_response = Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

        # Try to cache the parsed JSON
        try:
            json_body = json.loads(body.decode("utf-8"))
            _IDEMPOTENCY_STORE[store_key] = {
                "status": "done",
                "status_code": response.status_code,
                "response": json_body,
            }
        except Exception:
            # If not JSON, we can't easily safely cache it in this simple dict for JSONResponse.
            # We'll just remove the lock.
            _IDEMPOTENCY_STORE.pop(store_key, None)

        return new_response
