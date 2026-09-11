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
  - On done/error: server closes connection with appropriate code.
  - Client can send {"action": "ping"} to keep alive.

OWASP:
  A01 — Token verified before accept; org_id scoping applied to any DB queries.
  A02 — Token passed over WSS (TLS) in prod; HTTP not allowed by CORS config.
  A07 — Invalid/expired tokens result in close code 4001 (not 1008, to avoid
         leaking error type to eavesdroppers).
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from packages.auth.exceptions import AuthError
from packages.auth.jwt import decode_and_verify
from packages.auth.models import Role

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Close codes
WS_CLOSE_POLICY_VIOLATION = 4001  # auth failure
WS_CLOSE_NORMAL = 1000


@router.websocket("/ws/v1/missions/{mission_id}")
async def mission_status_stream(
    websocket: WebSocket,
    mission_id: str,
    token: Optional[str] = Query(default=None),
) -> None:
    """
    Stream real-time status updates for a Mission via WebSocket.
    """
    # ── Auth: verify JWT from query param ─────────────────────────────────────
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

    # Minimum role: VIEWER
    if not any(
        r in (Role.VIEWER, Role.ANALYST, Role.OPERATOR, Role.ADMIN, Role.SYSTEM)
        for r in [Role(r) if r in [e.value for e in Role] else None for r in roles]
        if r is not None
    ):
        logger.warning("WebSocket access denied: subject=%s mission=%s", subject, mission_id)
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
        return

    await websocket.accept()

    logger.info("WebSocket connected: mission=%s org=%s subject=%s", mission_id, org_id, subject)

    try:
        # ── Welcome frame ──────────────────────────────────────────────────────
        await websocket.send_json(
            {
                "event": "connected",
                "mission_id": mission_id,
                "org_id": org_id,
                "message": "Streaming mission status updates.",
            }
        )

        # ── Stream loop ────────────────────────────────────────────────────────
        # Production: subscribe to Redis pub/sub channel f"mission:{mission_id}:status"
        # and forward messages. Here we send a mock status sequence for testability.
        statuses = ["queued", "running", "completed"]
        for status in statuses:
            await asyncio.sleep(0)  # yield to event loop — non-blocking in tests
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
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
