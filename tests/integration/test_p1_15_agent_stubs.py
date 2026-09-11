"""
Integration tests for P1-15: Agent Stubs.
"""

import pytest
from fastapi.testclient import TestClient


from services.mission.domain.models import JobStatus
from services.mission.implementation import app
from services.mission.dependencies import get_job_repo, get_mission_repo
from services.mission.repositories.memory import InMemoryJobRepository, InMemoryMissionRepository

_mission_repo = InMemoryMissionRepository()
_job_repo = InMemoryJobRepository()

app.dependency_overrides[get_mission_repo] = lambda: _mission_repo
app.dependency_overrides[get_job_repo] = lambda: _job_repo

client = TestClient(app)


from datetime import datetime, timedelta  # noqa: E402
from jose import jwt  # noqa: E402
from packages.auth.config import get_auth_settings  # noqa: E402


def generate_test_token(sub: str, org_id: str, roles: list[str]) -> str:
    settings = get_auth_settings()
    now = datetime.utcnow()
    payload = {
        "sub": sub,
        "org_id": org_id,
        "roles": roles,
        "scopes": [],
        "iss": settings.issuer,
        "aud": settings.audience,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


@pytest.fixture
def system_token():
    return generate_test_token("agent-worker", "tenant_1", roles=["system"])


@pytest.fixture
def viewer_token():
    return generate_test_token("user-1", "tenant_1", roles=["viewer"])


@pytest.fixture
def operator_token():
    return generate_test_token("operator-1", "tenant_1", roles=["operator", "analyst"])


@pytest.mark.integration
def test_p1_15_agent_can_update_job_status(system_token, operator_token):
    # 1. First create a mission and run as OPERATOR to get a job_id
    headers = {"Authorization": f"Bearer {operator_token}"}

    resp_mission = client.post(
        "/api/v1/missions", json={"name": "Agent Test Mission", "aoi_ids": []}, headers=headers
    )
    print("Mission Response:", resp_mission.json())
    mission_id = resp_mission.json()["id"]

    resp_run = client.post(f"/api/v1/missions/{mission_id}/runs", headers=headers)
    print("Run Response:", resp_run.json())
    job_id = resp_run.json()["job_id"]

    # 2. Agent updates job status using SYSTEM role
    agent_headers = {"Authorization": f"Bearer {system_token}"}
    update_payload = {
        "status": JobStatus.RUNNING.value,
        "progress": 50.5,
        "result_data": {"features": 12},
    }

    resp_update = client.patch(
        f"/api/v1/jobs/{job_id}/agent-status", json=update_payload, headers=agent_headers
    )

    assert resp_update.status_code == 200
    assert resp_update.json()["status"] == JobStatus.RUNNING.value
    assert resp_update.json()["started_at"] is not None


@pytest.mark.integration
def test_p1_15_viewer_cannot_update_job_status(viewer_token):
    # Verify RBAC protection on agent endpoints
    headers = {"Authorization": f"Bearer {viewer_token}"}
    update_payload = {
        "status": JobStatus.COMPLETED.value,
        "progress": 100.0,
    }

    resp_update = client.patch(
        "/api/v1/jobs/some-job-id/agent-status", json=update_payload, headers=headers
    )
    print("Viewer 404 Error:", resp_update.json())
    assert resp_update.status_code == 403
