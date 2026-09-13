"""
packages/shared/middleware/idempotency.py — Idempotency Control (P1-12).

Intercepts POST and PATCH requests containing an `Idempotency-Key` header.
Caches the response so that duplicate requests return the same result instead
of re-executing state-mutating operations.
"""

import hashlib
import json
import logging
import os
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
import redis.asyncio as redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


async def get_redis_client():
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
        return client
    except Exception:
        return None


_IDEMPOTENCY_STORE: dict[str, Any] = {}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in ("POST", "PATCH"):
            return await call_next(request)

        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return await call_next(request)

        # To prevent key collision across tenants/users, mix the key with the authorization token
        auth_header = request.headers.get("Authorization", "")
        store_key = f"idem:{hashlib.sha256(f'{idem_key}:{auth_header}'.encode()).hexdigest()}"

        redis_client = await get_redis_client()

        if redis_client:
            try:
                state_json = await redis_client.get(store_key)
                if state_json:
                    state = json.loads(state_json)
                    if state["status"] == "in-progress":
                        logger.warning(
                            "Concurrent duplicate request for idempotency key: %s", idem_key
                        )
                        return JSONResponse(
                            status_code=409,
                            content={
                                "code": "CONCURRENT_REQUEST",
                                "message": (
                                    "A request with this Idempotency-Key "
                                    "is currently being processed."
                                ),
                                "retryable": True,
                            },
                        )
                    elif state["status"] == "done":
                        logger.info("Idempotent cache hit for key: %s", idem_key)
                        return JSONResponse(
                            status_code=state["status_code"],
                            content=state["response"],
                        )

                # Mark as in-progress (TTL 24 hours)
                await redis_client.set(
                    store_key, json.dumps({"status": "in-progress"}), ex=86400, nx=True
                )
            except Exception as e:
                logger.warning("Redis idempotency error: %s", e)
                redis_client = None  # Force fallback below

        if not redis_client:
            # Fallback to memory
            if store_key in _IDEMPOTENCY_STORE:
                state = _IDEMPOTENCY_STORE[store_key]
                if state["status"] == "in-progress":
                    return JSONResponse(
                        status_code=409,
                        content={
                            "code": "CONCURRENT_REQUEST",
                            "message": (
                                "A request with this Idempotency-Key "
                                "is currently being processed."
                            ),
                            "retryable": True,
                        },
                    )
                elif state["status"] == "done":
                    return JSONResponse(status_code=state["status_code"], content=state["response"])
            _IDEMPOTENCY_STORE[store_key] = {"status": "in-progress"}

        try:
            response = await call_next(request)
        except Exception:
            if redis_client:
                try:
                    await redis_client.delete(store_key)
                except Exception:
                    pass
            else:
                _IDEMPOTENCY_STORE.pop(store_key, None)
            raise

        body = b""
        if hasattr(response, "body_iterator"):
            async for chunk in getattr(response, "body_iterator"):  # type: ignore[union-attr]
                if isinstance(chunk, bytes):
                    body += chunk
                else:
                    body += chunk.encode()

        new_response = Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

        try:
            json_body = json.loads(body.decode("utf-8"))
            done_state = {
                "status": "done",
                "status_code": response.status_code,
                "response": json_body,
            }
            if redis_client:
                try:
                    await redis_client.set(store_key, json.dumps(done_state), ex=86400)
                except Exception:
                    pass
            else:
                _IDEMPOTENCY_STORE[store_key] = done_state
        except Exception:
            if redis_client:
                try:
                    await redis_client.delete(store_key)
                except Exception:
                    pass
            else:
                _IDEMPOTENCY_STORE.pop(store_key, None)

        return new_response
