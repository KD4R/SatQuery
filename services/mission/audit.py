"""
services/mission/audit.py — Durable structured audit log (P1-09).

Records every state-mutating action on Mission, AOI and Job entities as an
immutable, append-only, JSON-Lines file.  In production, this file is shipped
to a SIEM or centralized log aggregator.

Design:
  - Uses python-json-logger for structured output (no homegrown serializers).
  - All writes are sync (logging.FileHandler) — the logger is wrapped in an
    async adapter so callers can await it without blocking the event loop.
  - Never logs personally identifiable information beyond the JWT 'sub' claim
    (already present in auth tokens and needed for audit accountability).
  - File rotates at 50 MB (RotatingFileHandler) so disk usage is bounded.

OWASP:
  A09 — Security Logging and Monitoring Failures: every CREATE/UPDATE/DELETE
        event on a sensitive resource is captured with subject, org, timestamp
        and action outcome.
"""

import asyncio
import logging
import logging.handlers
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Optional structured JSON logging
try:
    from pythonjsonlogger import jsonlogger as _jl  # type: ignore
    _HAS_JSON_LOGGER = True
except ImportError:
    _HAS_JSON_LOGGER = False

# ── Audit log file location ───────────────────────────────────────────────────
_AUDIT_LOG_PATH: str = os.getenv(
    "AUDIT_LOG_PATH",
    str(Path(__file__).parent.parent.parent / "logs" / "audit.jsonl"),
)

# ── Module-level logger setup (done once) ─────────────────────────────────────
_audit_logger: Optional[logging.Logger] = None


def _build_audit_logger() -> logging.Logger:
    lg = logging.getLogger("satquery.audit")
    if lg.handlers:
        return lg  # already configured
    lg.setLevel(logging.INFO)
    lg.propagate = False  # Don't mix into root logger

    log_path = Path(_AUDIT_LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler: logging.Handler
    try:
        handler = logging.handlers.RotatingFileHandler(
            filename=str(log_path),
            maxBytes=50 * 1024 * 1024,  # 50 MB
            backupCount=10,
            encoding="utf-8",
        )
    except OSError:
        # Fallback to stderr if the file cannot be created (e.g. read-only fs in CI)
        handler = logging.StreamHandler()

    if _HAS_JSON_LOGGER:
        formatter = _jl.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
    else:
        formatter = logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
            '"message":"%(message)s"}'
        )
    handler.setFormatter(formatter)
    lg.addHandler(handler)
    return lg


def _get_audit_logger() -> logging.Logger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = _build_audit_logger()
    return _audit_logger


# ── Public API ─────────────────────────────────────────────────────────────────

def _build_record(
    action: str,
    resource_type: str,
    resource_id: str,
    subject: str,
    organisation_id: str,
    outcome: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "subject": subject,
        "organisation_id": organisation_id,
        "outcome": outcome,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        # Merge safe extra fields; never log raw user content > 256 chars
        for k, v in extra.items():
            if isinstance(v, str) and len(v) > 256:
                v = v[:256] + "…"
            record[k] = v
    return record


def log_action(
    action: str,
    resource_type: str,
    resource_id: str,
    subject: str,
    organisation_id: str,
    outcome: str = "SUCCESS",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Synchronously write one audit record.

    Args:
        action:           Verb — CREATE, UPDATE, DELETE, SUBMIT, CANCEL.
        resource_type:    Entity type — mission, aoi, job.
        resource_id:      Stable resource identifier.
        subject:          JWT 'sub' of the acting principal.
        organisation_id:  Tenant identifier.
        outcome:          SUCCESS or FAILURE.
        extra:            Additional safe key-value pairs to include.
    """
    record = _build_record(
        action, resource_type, resource_id, subject, organisation_id, outcome, extra
    )
    lg = _get_audit_logger()
    lg.info(
        "%s %s %s by %s (%s): %s",
        action,
        resource_type,
        resource_id,
        subject,
        organisation_id,
        outcome,
        extra=record,
    )


async def alog_action(
    action: str,
    resource_type: str,
    resource_id: str,
    subject: str,
    organisation_id: str,
    outcome: str = "SUCCESS",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Async-friendly wrapper — runs log_action in the default executor so the
    event loop is never blocked by synchronous file I/O.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        log_action,
        action,
        resource_type,
        resource_id,
        subject,
        organisation_id,
        outcome,
        extra,
    )
