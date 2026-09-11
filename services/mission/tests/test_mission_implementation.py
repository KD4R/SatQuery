from fastapi.testclient import TestClient
from services.mission.implementation import app

client = TestClient(app)

def test_monorepo_and_service_skeletons_valid():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "mission"}

def test_monorepo_and_service_skeletons_invalid_input():
    response = client.get("/api/v1/non_existent_route")
    assert response.status_code == 404
