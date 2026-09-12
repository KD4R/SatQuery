"""
Integration tests for P1-06: Mission CRUD endpoints.

Uses dependency overrides to inject shared in-memory repositories so all
tests in this module share state (mimics a real DB session per request-group).
Each test function resets state via fixtures.
"""

import pytest
from fastapi.testclient import TestClient

from packages.auth.tests.conftest import make_token
from services.mission.dependencies import get_aoi_repo, get_job_repo, get_mission_repo
from services.mission.implementation import app
from services.mission.repositories.memory import (
    InMemoryAOIRepository,
    InMemoryJobRepository,
    InMemoryMissionRepository,
)

ORG_A = "org-alpha"
ORG_B = "org-beta"
POINT_GEOM = {"type": "Point", "coordinates": [77.5946, 12.9716]}


def _token(roles=None, org_id=ORG_A):
    return make_token(roles=roles or ["analyst"], org_id=org_id)


def _auth(roles=None, org_id=ORG_A):
    return {"Authorization": f"Bearer {_token(roles=roles, org_id=org_id)}"}


@pytest.fixture()
def mission_app():
    """Return a fresh TestClient with isolated in-memory repos per test."""
    mission_repo = InMemoryMissionRepository()
    aoi_repo = InMemoryAOIRepository()
    job_repo = InMemoryJobRepository()
    app.dependency_overrides[get_mission_repo] = lambda: mission_repo
    app.dependency_overrides[get_aoi_repo] = lambda: aoi_repo
    app.dependency_overrides[get_job_repo] = lambda: job_repo
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── CREATE ────────────────────────────────────────────────────────────────────
@pytest.mark.integration
def test_p1_06_create_mission_returns_201(mission_app):
    resp = mission_app.post(
        "/api/v1/missions",
        json={"name": "Alpha Mission", "description": "test"},
        headers=_auth(),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Alpha Mission"
    assert body["status"] == "draft"
    assert body["organisation_id"] == ORG_A
    assert "id" in body


@pytest.mark.integration
def test_p1_06_create_mission_requires_auth(mission_app):
    resp = mission_app.post("/api/v1/missions", json={"name": "x"})
    assert resp.status_code == 401


@pytest.mark.integration
def test_p1_06_create_mission_viewer_gets_403(mission_app):
    resp = mission_app.post(
        "/api/v1/missions",
        json={"name": "x"},
        headers=_auth(roles=["viewer"]),
    )
    assert resp.status_code == 403


@pytest.mark.integration
def test_p1_06_create_mission_validates_empty_name(mission_app):
    resp = mission_app.post(
        "/api/v1/missions",
        json={"name": ""},
        headers=_auth(),
    )
    assert resp.status_code == 422


# ── READ ──────────────────────────────────────────────────────────────────────
@pytest.mark.integration
def test_p1_06_get_mission_returns_200(mission_app):
    created = mission_app.post(
        "/api/v1/missions",
        json={"name": "Bravo"},
        headers=_auth(),
    ).json()
    resp = mission_app.get(f"/api/v1/missions/{created['id']}", headers=_auth(roles=["viewer"]))
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


@pytest.mark.integration
def test_p1_06_get_mission_not_found_returns_404(mission_app):
    resp = mission_app.get("/api/v1/missions/nonexistent-id", headers=_auth(roles=["viewer"]))
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "MISSION_NOT_FOUND"


@pytest.mark.integration
def test_p1_06_list_missions_pagination(mission_app):
    for i in range(3):
        mission_app.post("/api/v1/missions", json={"name": f"M{i}"}, headers=_auth())
    resp = mission_app.get("/api/v1/missions?limit=2&offset=0", headers=_auth(roles=["viewer"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


# ── TENANT ISOLATION ──────────────────────────────────────────────────────────
@pytest.mark.integration
def test_p1_06_tenant_isolation_org_a_cannot_see_org_b_mission(mission_app):
    # Org B creates a mission
    mission_app.post(
        "/api/v1/missions",
        json={"name": "Secret"},
        headers=_auth(org_id=ORG_B),
    )
    # Org A lists — must see 0 missions
    resp = mission_app.get("/api/v1/missions", headers=_auth(org_id=ORG_A, roles=["viewer"]))
    assert resp.json()["total"] == 0


# ── UPDATE ────────────────────────────────────────────────────────────────────
@pytest.mark.integration
def test_p1_06_update_mission_returns_200(mission_app):
    m = mission_app.post("/api/v1/missions", json={"name": "Old"}, headers=_auth()).json()
    resp = mission_app.patch(
        f"/api/v1/missions/{m['id']}",
        json={"name": "New"},
        headers=_auth(roles=["operator"]),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"


@pytest.mark.integration
def test_p1_06_update_mission_analyst_gets_403(mission_app):
    m = mission_app.post("/api/v1/missions", json={"name": "x"}, headers=_auth()).json()
    resp = mission_app.patch(
        f"/api/v1/missions/{m['id']}",
        json={"name": "y"},
        headers=_auth(roles=["analyst"]),
    )
    assert resp.status_code == 403


# ── DELETE ────────────────────────────────────────────────────────────────────
@pytest.mark.integration
def test_p1_06_delete_mission_returns_204(mission_app):
    m = mission_app.post("/api/v1/missions", json={"name": "Del"}, headers=_auth()).json()
    resp = mission_app.delete(f"/api/v1/missions/{m['id']}", headers=_auth(roles=["admin"]))
    assert resp.status_code == 204


@pytest.mark.integration
def test_p1_06_delete_mission_non_admin_gets_403(mission_app):
    m = mission_app.post("/api/v1/missions", json={"name": "Del"}, headers=_auth()).json()
    resp = mission_app.delete(f"/api/v1/missions/{m['id']}", headers=_auth(roles=["operator"]))
    assert resp.status_code == 403


# ── AOI CRUD ──────────────────────────────────────────────────────────────────
@pytest.mark.integration
def test_p1_06_create_aoi_returns_201(mission_app):
    resp = mission_app.post(
        "/api/v1/aois",
        json={"name": "Bangalore AOI", "geometry": POINT_GEOM},
        headers=_auth(),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Bangalore AOI"
    assert body["geometry"]["type"] == "Point"


@pytest.mark.integration
def test_p1_06_create_aoi_invalid_geometry_type_returns_422(mission_app):
    resp = mission_app.post(
        "/api/v1/aois",
        json={"name": "x", "geometry": {"type": "InvalidType", "coordinates": []}},
        headers=_auth(),
    )
    assert resp.status_code == 422


@pytest.mark.integration
def test_p1_06_create_aoi_missing_geometry_type_returns_422(mission_app):
    resp = mission_app.post(
        "/api/v1/aois",
        json={"name": "x", "geometry": {"coordinates": [[0, 0]]}},
        headers=_auth(),
    )
    assert resp.status_code == 422


@pytest.mark.integration
def test_p1_06_aoi_tenant_isolation(mission_app):
    mission_app.post(
        "/api/v1/aois",
        json={"name": "AOI-B", "geometry": POINT_GEOM},
        headers=_auth(org_id=ORG_B),
    )
    resp = mission_app.get("/api/v1/aois", headers=_auth(org_id=ORG_A, roles=["viewer"]))
    assert resp.json()["total"] == 0


@pytest.mark.integration
def test_p1_06_delete_aoi_returns_204(mission_app):
    aoi = mission_app.post(
        "/api/v1/aois",
        json={"name": "X", "geometry": POINT_GEOM},
        headers=_auth(),
    ).json()
    resp = mission_app.delete(f"/api/v1/aois/{aoi['id']}", headers=_auth(roles=["operator"]))
    assert resp.status_code == 204


# ── JOB LIFECYCLE (P1-07) ──────────────────────────────────────────────────────
@pytest.mark.integration
def test_p1_07_submit_run_returns_202(mission_app):
    m = mission_app.post("/api/v1/missions", json={"name": "Run Me"}, headers=_auth()).json()
    resp = mission_app.post(
        f"/api/v1/missions/{m['id']}/runs",
        headers=_auth(roles=["operator"]),
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["mission_id"] == m["id"]


@pytest.mark.integration
def test_p1_07_submit_run_analyst_gets_403(mission_app):
    m = mission_app.post("/api/v1/missions", json={"name": "x"}, headers=_auth()).json()
    resp = mission_app.post(
        f"/api/v1/missions/{m['id']}/runs",
        headers=_auth(roles=["analyst"]),
    )
    assert resp.status_code == 403


@pytest.mark.integration
def test_p1_07_submit_run_nonexistent_mission_returns_404(mission_app):
    resp = mission_app.post(
        "/api/v1/missions/bad-id/runs",
        headers=_auth(roles=["operator"]),
    )
    assert resp.status_code == 404


@pytest.mark.integration
def test_p1_07_poll_job_status_returns_200(mission_app):
    m = mission_app.post("/api/v1/missions", json={"name": "Poll"}, headers=_auth()).json()
    job = mission_app.post(
        f"/api/v1/missions/{m['id']}/runs",
        headers=_auth(roles=["operator"]),
    ).json()
    resp = mission_app.get(
        f"/api/v1/jobs/{job['job_id']}",
        headers=_auth(roles=["viewer"]),
    )
    assert resp.status_code == 200
    assert resp.json()["mission_id"] == m["id"]


@pytest.mark.integration
def test_p1_07_poll_job_unknown_id_returns_404(mission_app):
    resp = mission_app.get("/api/v1/jobs/bad-job-id", headers=_auth(roles=["viewer"]))
    assert resp.status_code == 404
