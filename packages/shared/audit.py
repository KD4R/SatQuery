import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel

logger = logging.getLogger("satquery.audit")


class AuditEvent(BaseModel):
    timestamp: str
    actor_id: str
    organisation_id: str
    action: str
    resource_type: str
    resource_id: str
    trace_id: Optional[str] = None
    details: Dict[str, Any] = {}


class AuditLogger:
    """
    Structured audit logger for compliance and traceability (P1-09).
    Logs are emitted to stdout as JSON for OpenTelemetry/FluentBit scraping.
    In a high-compliance production environment, this could also write directly
    to a Kafka topic or an immutable Postgres table.
    """

    @staticmethod
    def log_event(
        actor_id: str,
        organisation_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        trace_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor_id=actor_id,
            organisation_id=organisation_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            trace_id=trace_id,
            details=details or {},
        )
        # Log as structured JSON
        logger.info(json.dumps(event.model_dump()))
