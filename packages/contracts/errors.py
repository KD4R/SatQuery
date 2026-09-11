from typing import List, Optional
from pydantic import BaseModel, Field

class ErrorDetail(BaseModel):
    message: str
    code: str

class ErrorResponse(BaseModel):
    """
    Canonical ErrorResponse: code, message, details[], retryable, trace_id.
    """
    code: str = Field(..., description="High-level error code")
    message: str = Field(..., description="Human-readable error message")
    details: List[ErrorDetail] = Field(default_factory=list, description="List of specific error details")
    retryable: bool = Field(default=False, description="Indicates if the operation can be retried")
    trace_id: Optional[str] = Field(default=None, description="Correlation trace ID")
