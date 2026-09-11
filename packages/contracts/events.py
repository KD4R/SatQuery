from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc)


class EventEnvelope(BaseModel):
    """
    Canonical EventEnvelope for inter-service async events.
    """

    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="Type of event (e.g., INFERENCE_COMPLETED)")
    timestamp: datetime = Field(default_factory=utc_now, description="Event occurrence time")
    trace_id: Optional[str] = Field(default=None, description="Correlation trace ID")
    mission_id: Optional[str] = Field(default=None, description="Associated mission ID")
    producer: str = Field(..., description="Service producing the event")
    schema_version: str = Field(default="1.0", description="Schema version")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event-specific payload")
