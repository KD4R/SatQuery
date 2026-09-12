"""
security/exceptions.py — Security exception hierarchy for SatQuery AI Agent.
"""


class SecurityError(Exception):
    """Base exception for security check failures."""

    def __init__(self, message: str, code: str = "SECURITY_VIOLATION"):
        super().__init__(message)
        self.message = message
        self.code = code


class PromptInjectionError(SecurityError):
    """Raised when an untrusted input contains prompt injection patterns."""

    def __init__(self, message: str = "Potential prompt injection detected in input"):
        super().__init__(message=message, code="PROMPT_INJECTION_DETECTED")


class GeometryValidationError(SecurityError):
    """Raised when GeoJSON or AOI bounds are invalid."""

    def __init__(self, message: str):
        super().__init__(message=message, code="INVALID_GEOMETRY")


class BudgetExceededError(SecurityError):
    """Raised when a tool call exceeds allocated quota or budget."""

    def __init__(self, message: str = "Tool execution budget exceeded"):
        super().__init__(message=message, code="BUDGET_EXCEEDED")


class ToolPermissionDeniedError(SecurityError):
    """Raised when caller lacks permission to execute a tool."""

    def __init__(self, message: str = "Permission denied for tool execution"):
        super().__init__(message=message, code="TOOL_PERMISSION_DENIED")
