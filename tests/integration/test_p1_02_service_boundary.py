from fastapi.testclient import TestClient
from services.gateway.implementation import app as gateway_app
from services.mission.implementation import app as mission_app

gateway_client = TestClient(gateway_app)
mission_client = TestClient(mission_app)


def test_p1_02_service_boundary():
    # Simple boundaries test for P1-02 to ensure routing/apps are insulated
    gw_resp = gateway_client.get("/api/v1/health")
    assert gw_resp.status_code == 200

    ms_resp = mission_client.get("/api/v1/health")
    assert ms_resp.status_code == 200
