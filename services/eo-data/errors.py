from pydantic import BaseModel
from typing import List, Optional


class ErrorResponse(BaseModel):
    """Canonical ErrorResponse as defined in Engineering Rules."""

    code: str
    message: str
    details: List[str]
    retryable: bool
    trace_id: str
    mission_id: Optional[str] = None
    run_id: Optional[str] = None
    job_id: Optional[str] = None
    organization_id: Optional[str] = None
