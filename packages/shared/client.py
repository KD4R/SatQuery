"""
packages/shared/client.py — Internal HTTP Client for Service-to-Service communication.

OWASP Mitigations:
  - Validates API responses and extracts standard ErrorResponse objects
    preventing application crashes from unexpected downstream HTML/text errors.
  - Generates scoped short-lived JWTs (P1-11) for internal authentication.
"""

from typing import Any, Dict, List
import httpx

from packages.auth.jwt import generate_s2s_token
from packages.auth.models import AuthContext
from packages.contracts.errors import ErrorResponse


class InternalClientError(Exception):
    """Raised when an internal downstream service returns a 4xx/5xx error."""

    def __init__(self, status_code: int, error_response: ErrorResponse):
        self.status_code = status_code
        self.error = error_response
        super().__init__(f"Internal client error {status_code}: {error_response.message}")


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
        self.client = httpx.AsyncClient(base_url=self.base_url)

    def _get_headers(self, auth_context: AuthContext) -> Dict[str, str]:
        # Generate a short-lived internal JWT with requested scopes
        # and bound to the same tenant (org_id) as the caller context.
        token = generate_s2s_token(
            caller_service=self.caller_service,
            org_id=auth_context.organisation_id,
            scopes=self.scopes,
        )
        return {"Authorization": f"Bearer {token}"}

    async def _request(
        self, method: str, path: str, auth_context: AuthContext, **kwargs: Any
    ) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        headers.update(self._get_headers(auth_context))

        response = await self.client.request(method, path, headers=headers, **kwargs)

        if response.is_error:
            # Map standard errors to InternalClientError
            try:
                error_data = response.json()
                # Assuming downstream follows our canonical ErrorResponse format
                error_response = ErrorResponse(**error_data)
            except Exception:
                # Fallback if downstream returned non-JSON or weird format
                error_response = ErrorResponse(
                    code="UPSTREAM_ERROR",
                    message=f"Upstream service returned {response.status_code}",
                    retryable=response.status_code >= 500,
                )
            raise InternalClientError(
                status_code=response.status_code, error_response=error_response
            )

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
