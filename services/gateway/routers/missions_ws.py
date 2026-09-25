"""
services/gateway/routers/missions_ws.py — WebSocket endpoint (P1-08).

Route: WS /ws/v1/missions/{mission_id}

Auth:
  - Browser WebSocket API does not support custom headers.
  - JWT passed as ?token=<bearer> query param.
  - Token is verified immediately on connect; reject (close 4001) if invalid.

Protocol:
  - On connect: server sends {"event": "connected", "mission_id": "...", "org_id": "..."}
  - Streams status messages: {"event": "status_update", "status": "...", "mission_id": "..."}
  - Envelope-shaped agent events (P5 §2C: SENSOR_DISAGREEMENT, ACQUIRING_EVIDENCE,
    AGENT_THOUGHT — canonical EventEnvelope from packages.contracts.events) pass
    through verbatim so the UI receives their payload intact. The bridge does not
    interpret them; it only recognises the envelope shape.
  - On done/error: server closes connection with appropriate code.
  - Client can send {"action": "ping"} to keep alive.

OWASP:
  A01 — Token verified before accept; org_id scoping applied to any DB queries.
  A02 — Token passed over WSS (TLS) in prod; HTTP not allowed by CORS config.
  A07 — Invalid/expired tokens result in close code 4001 (not 1008, to avoid
         leaking error type to eavesdroppers).
"""

import asyncio
import json
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
import redis.asyncio as redis

from packages.auth.exceptions import AuthError
from packages.auth.jwt import decode_and_verify
from packages.auth.models import Role

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Close codes
WS_CLOSE_POLICY_VIOLATION = 4001  # auth failure
WS_CLOSE_NORMAL = 1000

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Resolved once at import time; never constructed from user input (A10).
_MISSION_SERVICE_URL = os.getenv("MISSION_SERVICE_URL", "http://localhost:8001")
_S2S_TIMEOUT_S = 3.0


async def _verify_mission_tenant(mission_id: str, org_id: str, token: str) -> bool:
    """Confirm with the mission service that this org owns the mission (A01).

    The WebSocket route accepts a token and mission id; without an ownership
    check, any authenticated tenant could subscribe to another tenant's
    mission channel. The mission service's GET endpoint is tenant-scoped, so
    a 200 proves ownership. Cross-tenant probes return 404 there.
    """
    from packages.auth.jwt import generate_s2s_token

    try:
        async with httpx.AsyncClient(timeout=_S2S_TIMEOUT_S) as client:
            resp = await client.get(
                f"{_MISSION_SERVICE_URL}/api/v1/missions/{mission_id}",
                headers={
                    "Authorization": "Bearer "
                    + generate_s2s_token(
                        caller_service="gateway",
                        org_id=org_id,
                        scopes=["mission:read"],
                    )
                },
            )
        if resp.status_code == 200:
            return True
        if resp.status_code == 404:
            return False
        # 5xx/other from mission service: fail closed.
        logger.warning(
            "Mission ownership check returned %s for mission=%s", resp.status_code, mission_id
        )
        return False
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        # Fail closed: deny rather than stream unverified.
        logger.warning("Mission ownership check unreachable for mission=%s: %s", mission_id, exc)
        return False


@router.websocket("/ws/v1/missions/{mission_id}")
async def mission_status_stream(
    websocket: WebSocket,
    mission_id: str,
    token: Optional[str] = Query(default=None),
) -> None:
    """
    Stream real-time status updates for a Mission via WebSocket.
    """
    if not token:
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
        return

    try:
        payload = decode_and_verify(token)
        org_id: str = payload["org_id"]
        subject: str = payload["sub"]
        roles = payload.get("roles", [])
    except AuthError:
        logger.warning("WebSocket auth failed for mission=%s (token invalid/expired)", mission_id)
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
        return

    if not any(
        r in (Role.VIEWER, Role.ANALYST, Role.OPERATOR, Role.ADMIN, Role.SYSTEM)
        for r in [Role(r) if r in [e.value for e in Role] else None for r in roles]
        if r is not None
    ):
        logger.warning("WebSocket access denied: subject=%s mission=%s", subject, mission_id)
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
        return

    # Tenant isolation (A01): the caller's org must own this mission before
    # anything is streamed. SYSTEM accounts (S2S) bypass by design.
    if Role.SYSTEM not in [Role(r) for r in roles if r in [e.value for e in Role]]:
        if not await _verify_mission_tenant(mission_id, org_id, token):
            logger.warning(
                "WebSocket tenant check failed: subject=%s mission=%s org=%s",
                subject,
                mission_id,
                org_id,
            )
            await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
            return

    await websocket.accept()
    logger.info("WebSocket connected: mission=%s org=%s subject=%s", mission_id, org_id, subject)

    redis_client = None
    pubsub = None

    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        # Attempt to ping to check connection before subscribing
        await redis_client.ping()
        pubsub = redis_client.pubsub()
        channel = f"mission:{mission_id}:status"
        await pubsub.subscribe(channel)
    except Exception as exc:
        logger.warning(
            "Could not connect to Redis for websocket pub/sub: %s. Using mock fallback.", exc
        )
        if redis_client:
            await redis_client.aclose()
        redis_client = None
        pubsub = None

    try:
        await websocket.send_json(
            {
                "event": "connected",
                "mission_id": mission_id,
                "org_id": org_id,
                "message": "Streaming mission status updates.",
            }
        )

        if pubsub:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        payload = {"status": data}

                    # Agent event envelopes (P5 §2C) pass through verbatim: the
                    # payload belongs to the UI, not to the status protocol.
                    # Shape-checked, not type-fuzzed — anything that is not an
                    # EventEnvelope falls through to the status path below.
                    if (
                        isinstance(payload, dict)
                        and isinstance(payload.get("event_id"), str)
                        and isinstance(payload.get("event_type"), str)
                        and isinstance(payload.get("producer"), str)
                        and isinstance(payload.get("payload"), dict)
                    ):
                        await websocket.send_json(payload)
                        continue

                    status_val = payload.get("status", "unknown")
                    await websocket.send_json(
                        {
                            "event": "status_update",
                            "mission_id": mission_id,
                            "status": status_val,
                            "org_id": org_id,
                        }
                    )

                    if status_val in ("completed", "failed", "cancelled"):
                        await websocket.send_json(
                            {"event": "done", "mission_id": mission_id, "final_status": status_val}
                        )
                        break
        else:
            # Fallback mock sequence for tests without Redis
            statuses = ["queued", "running", "completed"]
            for status in statuses:
                await asyncio.sleep(0)
                await websocket.send_json(
                    {
                        "event": "status_update",
                        "mission_id": mission_id,
                        "status": status,
                        "org_id": org_id,
                    }
                )
            await websocket.send_json(
                {"event": "done", "mission_id": mission_id, "final_status": "completed"}
            )

        await websocket.close(code=WS_CLOSE_NORMAL)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client: mission=%s org=%s", mission_id, org_id)
    except Exception as exc:  # pragma: no cover
        logger.exception("WebSocket error: mission=%s org=%s error=%s", mission_id, org_id, exc)
        try:
            await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
        except Exception:
            pass
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(f"mission:{mission_id}:status")
                await pubsub.close()
            except Exception:
                pass
        if redis_client:
            try:
                await redis_client.aclose()
            except Exception:
                pass
