"""
tests/integration/test_p1_15_agent_stubs.py
Integration tests for P1-15: Mission <-> Agent integration stubs.

Verifies:
  - SYSTEM-scoped token can update a job via the agent-status endpoint.
  - Standard VIEWER-scoped token is rejected with 403 Forbidden.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from packages.auth.config import get_auth_settings
from services.mission.dependencies import get_job_repo, get_mission_repo
from services.mission.domain.models import JobStatus
from services.mission.implementation import app
from services.mission.repositories.memory import (
    InMemoryJobRepository,
    InMemoryMissionRepository,
)

# ── Token helpers ─────────────────────────────────────────────────────────────


def _make_token(sub: str, org_id: str, roles: list) -> str:
    """Mint a short-lived HS256 test token with explicit roles."""
    settings = get_auth_settings()
    now = datetime.utcnow()
    payload: dict = {
        "sub": sub,
        "org_id": org_id,
        "roles": roles,
        "scopes": [],
        "iss": settings.issuer,
        "aud": settings.audience,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return str(jwt.encode(payload, settings.secret_key, algorithm="HS256"))


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def fresh_repos():
    """
    Provide isolated, per-test in-memory repositories.
    Override FastAPI dependency injectors so every test starts with clean state
    and cross-test pollution is impossible.
    """
    mission_repo = InMemoryMissionRepository()
    job_repo = InMemoryJobRepository()
    app.dependency_overrides[get_mission_repo] = lambda: mission_repo
    app.dependency_overrides[get_job_repo] = lambda: job_repo
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def http() -> TestClient:
    """Return a TestClient bound to the mission app."""
    return TestClient(app)


@pytest.fixture()
def system_token() -> str:
    return _make_token("svc:agent-worker", "tenant_1", roles=["system"])


@pytest.fixture()
def viewer_token() -> str:
    return _make_token("user:viewer-1", "tenant_1", roles=["viewer"])


@pytest.fixture()
def operator_token() -> str:
    # OPERATOR inherits ANALYST permissions in our RBAC model.
    return _make_token("user:operator-1", "tenant_1", roles=["operator", "analyst"])


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_p1_15_agent_can_update_job_status(http, system_token, operator_token):
    """
    Happy path: A SYSTEM-scoped agent can transition a pending job to RUNNING.
    """
    op_headers = {"Authorization": f"Bearer {operator_token}"}

    # 1. Create a mission
    resp = http.post(
        "/api/v1/missions",
        json={"name": "Agent Integration Mission", "aoi_ids": []},
        headers=op_headers,
    )
    assert resp.status_code == 201, resp.json()
    mission_id = resp.json()["id"]

    # 2. Submit a run to get a job_id
    resp = http.post(f"/api/v1/missions/{mission_id}/runs", headers=op_headers)
    assert resp.status_code == 202, resp.json()
    job_id = resp.json()["job_id"]

    # 3. Agent marks job as RUNNING with 50% progress
    agent_headers = {"Authorization": f"Bearer {system_token}"}
    resp = http.patch(
        f"/api/v1/jobs/{job_id}/agent-status",
        json={
            "status": JobStatus.RUNNING.value,
            "progress": 50.0,
            "result_data": {"bands_processed": 6},
        },
        headers=agent_headers,
    )
    assert resp.status_code == 200, resp.json()
    body = resp.json()
    assert body["status"] == JobStatus.RUNNING.value
    assert body["started_at"] is not None


@pytest.mark.integration
def test_p1_15_viewer_cannot_update_job_status(http, viewer_token):
    """
    Security: VIEWER-scoped token must be rejected with 403 Forbidden.
    OWASP A01 — Broken Access Control: non-system callers must never mutate agent state.
    """
    headers = {"Authorization": f"Bearer {viewer_token}"}
    resp = http.patch(
        "/api/v1/jobs/nonexistent-job-id/agent-status",
        json={"status": JobStatus.COMPLETED.value, "progress": 100.0},
        headers=headers,
    )
    # Auth check happens before the job lookup — must be 403, not 404.
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "INSUFFICIENT_PERMISSIONS"
