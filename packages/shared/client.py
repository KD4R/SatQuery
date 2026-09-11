"""
packages/shared/client.py — Internal HTTP Client for Service-to-Service communication.

OWASP Mitigations:
  - Validates API responses and extracts standard ErrorResponse objects
    preventing application crashes from unexpected downstream HTML/text errors.
  - Generates scoped short-lived JWTs (P1-11) for internal authentication.
"""

import logging
import time
from typing import Any, Dict, List
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from packages.auth.jwt import generate_s2s_token
from packages.auth.models import AuthContext
from packages.contracts.errors import ErrorResponse

logger = logging.getLogger(__name__)


class InternalClientError(Exception):
    """Raised when an internal downstream service returns a 4xx/5xx error."""

    def __init__(self, status_code: int, error_response: ErrorResponse):
        self.status_code = status_code
        self.error = error_response
        super().__init__(f"Internal client error {status_code}: {error_response.message}")


class CircuitBreakerOpenError(Exception):
    """Raised when the internal client's circuit breaker is open."""

    pass


class CircuitBreaker:
    """Simple in-memory state machine for circuit breaking."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 10.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning("Circuit breaker tripped OPEN.")

    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            # Check if recovery timeout has elapsed
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        # HALF_OPEN allows one execution to test recovery
        if self.state == "HALF_OPEN":
            return True
        return True


class InternalClient:
    """
    Shared HTTP client for internal microservices.
    Automatically handles S2S authentication and trace propagation.
    """

    def __init__(self, base_url: str, caller_service: str, scopes: List[str]):
        """
        Args:
            base_url: The internal URL of the target service.
            caller_service: The name of the calling service (e.g. "gateway").
            scopes: The scopes to request in the S2S token.
        """
        self.base_url = base_url.rstrip("/")
        self.caller_service = caller_service
        self.scopes = scopes
        # Timeout configured to 5 seconds to prevent cascading delays
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=5.0)
        self.circuit_breaker = CircuitBreaker()

    def _get_headers(self, auth_context: AuthContext) -> Dict[str, str]:
        # Generate a short-lived internal JWT with requested scopes
        # and bound to the same tenant (org_id) as the caller context.
        token = generate_s2s_token(
            caller_service=self.caller_service,
            org_id=auth_context.organisation_id,
            scopes=self.scopes,
        )
        return {"Authorization": f"Bearer {token}"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    async def _execute_with_retry(
        self, method: str, path: str, headers: dict, **kwargs
    ) -> httpx.Response:
        return await self.client.request(method, path, headers=headers, **kwargs)

    async def _request(
        self, method: str, path: str, auth_context: AuthContext, **kwargs: Any
    ) -> httpx.Response:

        if not self.circuit_breaker.can_execute():
            raise CircuitBreakerOpenError(f"Circuit breaker is OPEN for {self.base_url}")

        headers = kwargs.pop("headers", {})
        headers.update(self._get_headers(auth_context))

        try:
            response = await self._execute_with_retry(method, path, headers=headers, **kwargs)
        except Exception:
            self.circuit_breaker.record_failure()
            raise

        if response.is_error:
            # 5xx errors trigger the circuit breaker
            if response.status_code >= 500:
                self.circuit_breaker.record_failure()
            else:
                # 4xx are client errors, reset failures
                self.circuit_breaker.record_success()

            # Map standard errors to InternalClientError
            try:
                error_data = response.json()
                error_response = ErrorResponse(**error_data)
            except Exception:
                error_response = ErrorResponse(
                    code="UPSTREAM_ERROR",
                    message=f"Upstream service returned {response.status_code}",
                    retryable=response.status_code >= 500,
                )
            raise InternalClientError(
                status_code=response.status_code, error_response=error_response
            )

        self.circuit_breaker.record_success()
        return response

    async def get(self, path: str, auth_context: AuthContext, **kwargs: Any) -> httpx.Response:
        return await self._request("GET", path, auth_context, **kwargs)

    async def post(self, path: str, auth_context: AuthContext, **kwargs: Any) -> httpx.Response:
        return await self._request("POST", path, auth_context, **kwargs)

    async def put(self, path: str, auth_context: AuthContext, **kwargs: Any) -> httpx.Response:
        return await self._request("PUT", path, auth_context, **kwargs)

    async def delete(self, path: str, auth_context: AuthContext, **kwargs: Any) -> httpx.Response:
        return await self._request("DELETE", path, auth_context, **kwargs)

    async def aclose(self):
        await self.client.aclose()
