"""The real model through the real HTTP stack (P3 inference work pack).

App, lifespan warm-up, bearer auth, registry with manifests required, the
committed checkpoint, a real Sentinel-1 chip, and a storage sink -- nothing
patched, everything swapped only through ``dependency_overrides``.

Skips unless the weights and the chip are present, because both are deliberately
not committed: weights travel by checksum (ml/scripts/fetch_model.py) and the
Sen1Floods11 chips are 533 MB. On a machine that has them -- a developer's, the
inference image with data mounted -- this is the test that proves the service
actually serves the model rather than the baseline.

    PYTHONPATH="$PWD" python ml/scripts/fetch_model.py hand-only-v2 --from <dir>
    PYTHONPATH="$PWD" pytest services/inference/tests/test_live_inference_http.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.inference.artifacts import LocalArtifactSink
from services.inference.dependencies import (
    get_analysis_service,
    get_artifact_sink,
    get_raster_source,
    get_registry,
)
from services.inference.implementation import app
from services.inference.registry import ModelRegistry
from services.inference.service import AnalysisService
from services.inference.sources import LocalRasterSource

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
MODELS = REPO_ROOT / "artifacts"
CHIPS = REPO_ROOT / "data" / "sen1floods11"
STEM = "India_533192"  # Brahmaputra floodplain, Nagaon, Assam


def _require(path: Path, why: str) -> Path:
    if not path.is_file():
        pytest.skip(f"{path.relative_to(REPO_ROOT)} not present: {why}")
    return path


@pytest.fixture
def live(tmp_path: Path):
    pytest.importorskip("torch", reason="the live model needs requirements-ml.txt")
    _require(MODELS / "hand-only-v2" / "best.pt", "weights are fetched, not committed")
    scene = _require(CHIPS / "S1Hand" / f"{STEM}_S1Hand.tif", "Sen1Floods11 is not committed")
    jrc = _require(CHIPS / "JRCWaterHand" / f"{STEM}_JRCWaterHand.tif", "as above")

    # Copied, not symlinked: LocalRasterSource resolves every href and refuses one
    # that lands outside its root, and a symlink into the repo does exactly that.
    # (It did, the first time this test ran -- the guard working as designed.)
    chips = tmp_path / "chips"
    chips.mkdir()
    shutil.copyfile(scene, chips / scene.name)
    shutil.copyfile(jrc, chips / jrc.name)
    store = tmp_path / "store"

    # require_manifest=True: exactly what the inference image runs with.
    registry = ModelRegistry(
        MODELS, manifest_root=REPO_ROOT / "infrastructure/models", require_manifest=True
    )
    sink = LocalArtifactSink(store)
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_raster_source] = lambda: LocalRasterSource(chips)
    app.dependency_overrides[get_artifact_sink] = lambda: sink
    app.dependency_overrides[get_analysis_service] = lambda: AnalysisService(
        registry=registry,
        source=LocalRasterSource(chips),
        code_version="test",
        artifacts=sink,
    )
    try:
        with TestClient(app) as client:
            yield client, store, scene.name, jrc.name
    finally:
        app.dependency_overrides.clear()


def _auth(role: str) -> dict[str, str]:
    # Through test_api's helper, which is the one test-only cross-service import
    # .importlinter allows (services.inference -> services.agent's token helper).
    # Importing the agent helper here directly would add a second exception to the
    # boundary contract for no gain.
    from services.inference.tests.test_api import auth

    return auth(role)


def test_the_model_runs_not_the_baseline(live) -> None:
    client, store, scene_name, jrc_name = live
    response = client.post(
        "/api/v1/inference/analyses",
        headers=_auth("analyst"),
        json={
            "scene": {
                "provider": "sen1floods11",
                "collection": "sen1floods11-hand",
                "item_id": STEM,
                # Sen1Floods11 ships no per-chip timestamp; this is a test input only.
                "acquired_at": "2017-08-01T00:00:00Z",
                "platform": "sentinel-1",
                "instrument": "c-sar",
                "relative_orbit": None,
                "pass_direction": None,
                "href": scene_name,
                "cloud_cover": None,
            },
            "scene_href": scene_name,
            "permanent_water_href": jrc_name,
        },
    )
    assert response.status_code == 200, response.text
    analysis = response.json()

    # 1. The learned model produced it, verified, with no fallback.
    assert analysis["outcome"] == "analysed", analysis.get("explanation")
    assert analysis["degraded_from"] is None
    assert any(c.startswith("produced by hand-only-v2@") for c in analysis["caveats"])
    assert not any("not verified" in c for c in analysis["caveats"])

    # 2. Confidence reflects the calibration that was actually measured.
    confidence = analysis["confidence"]
    assert confidence["basis"] == "not_calibrated"
    assert confidence["value"] is None
    assert any("did not pass" in c for c in confidence["caveats"])

    # 3. The mask and polygons were kept, and agree with the reported area.
    area = float(analysis["measurements"][0]["value"])
    geojson = json.loads((store / analysis["geometry_ref"]).read_text())
    assert sum(f["properties"]["area_ha"] for f in geojson["features"]) == pytest.approx(
        area, abs=0.05
    )
    assert (store / analysis["raster_refs"][0]).stat().st_size > 0


def test_models_endpoint_reports_calibration(live) -> None:
    client, *_ = live
    body = client.get("/api/v1/inference/models", headers=_auth("viewer")).json()
    assert body["default"] == "hand-only-v2"
    card = next(m for m in body["models"] if m["name"] == "hand-only-v2")
    assert card["calibration_passes"] is False
    assert card["calibration_ece"] == pytest.approx(0.0583, abs=1e-4)
    assert card["checksum_verified"] is True, "warmed at startup, so verified by now"
