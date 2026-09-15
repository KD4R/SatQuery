"""Tests for the inference API (P3-01).

Exercised through the real HTTP stack with ``TestClient`` rather than by calling
the service object directly. Auth, request validation and — most importantly —
serialisation of the ``Analysis | Abstention`` union all live in that layer, and a
contract that validates in Python but serialises wrong is exactly the defect P5
would discover at integration.

Rasters are written by the test with rasterio into ``tmp_path``: real GeoTIFFs,
real CRS, real transforms, generated in-process so no fixture asset exists that a
product path could load.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from packages.contracts import Provider
from ml.io.preflight import PreflightError
from services.inference.dependencies import (
    get_analysis_service,
    get_raster_source,
    get_registry,
)
from services.inference.implementation import app
from services.inference.registry import ModelRegistry, ModelUnavailable
from services.inference.service import AnalysisService
from services.inference.sources import LocalRasterSource

pytestmark = pytest.mark.unit


def write_scene(path: Path, *, water_rows: int = 20, size: int = 64) -> Path:
    """A real two-band GeoTIFF in UTM with a separable dark region."""
    rng = np.random.default_rng(0)
    vv = rng.normal(-8.0, 1.0, (size, size)).astype(np.float32)
    vv[:water_rows, :] = rng.normal(-20.0, 1.0, (water_rows, size))
    bands = np.stack([vv, vv - 6.0])

    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=size,
        width=size,
        count=2,
        dtype="float32",
        crs="EPSG:32643",
        transform=from_origin(500000.0, 1000000.0, 10.0, 10.0),
    ) as sink:
        sink.write(bands)
        sink.set_band_description(1, "VV")
        sink.set_band_description(2, "VH")
    return path


SCENE = {
    "provider": (
        Provider.SEN1FLOODS11.value
        if hasattr(Provider, "SEN1FLOODS11")
        else Provider.ASF_HYP3.value
    ),
    "collection": "sen1floods11",
    "item_id": "India_1050276",
    "acquired_at": datetime(2026, 8, 12, tzinfo=timezone.utc).isoformat(),
    "platform": "Sentinel-1A",
    "instrument": "C-SAR",
    "relative_orbit": 77,
    "pass_direction": "ASCENDING",
    "href": "https://datapool.asf.alaska.edu/x.tif",
}


@pytest.fixture
def client(tmp_path: Path):
    """A client whose raster source and registry point at a temporary directory.

    Overridden through ``dependency_overrides`` rather than by patching, so the
    request still travels the whole real stack.
    """
    write_scene(tmp_path / "scene.tif")

    app.dependency_overrides[get_raster_source] = lambda: LocalRasterSource(tmp_path)
    app.dependency_overrides[get_registry] = lambda: ModelRegistry(tmp_path / "models")
    app.dependency_overrides[get_analysis_service] = lambda: AnalysisService(
        registry=ModelRegistry(tmp_path / "models"),
        source=LocalRasterSource(tmp_path),
        code_version="test",
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth(role: str = "analyst") -> dict[str, str]:
    """A bearer token for the repo's HS256 test configuration (root conftest).

    Uses the repository's own helper rather than minting a token here, so these
    tests break if the auth contract changes -- which is the point of testing
    through the real stack.
    """
    from services.agent.tests.helpers.test_tokens import make_test_token

    return {"Authorization": "Bearer " + make_test_token(roles=[role])}


# --------------------------------------------------------------------------- #
# Health                                                                       #
# --------------------------------------------------------------------------- #


def test_health_needs_no_auth(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "inference"}


def test_health_does_not_depend_on_a_model_being_loadable(client: TestClient) -> None:
    """Model availability is a degradation, not an outage.

    Reporting unhealthy with no model would pull the service out of rotation
    while it is perfectly able to serve baseline analyses.
    """
    assert client.get("/api/v1/health").json()["status"] == "ok"


# --------------------------------------------------------------------------- #
# Auth                                                                         #
# --------------------------------------------------------------------------- #


def test_analysis_requires_a_token(client: TestClient) -> None:
    response = client.post("/api/v1/inference/analyses", json={})
    assert response.status_code == 401


def test_analysis_requires_analyst_not_viewer(client: TestClient) -> None:
    """Running an analysis consumes compute and produces a reportable number.

    ANALYST is the role the platform defines as "can run analyses"; VIEWER is
    read-only and must not be able to trigger one.
    """
    response = client.post(
        "/api/v1/inference/analyses",
        json={"scene": SCENE, "scene_href": "scene.tif"},
        headers=auth("viewer"),
    )
    assert response.status_code == 403


def test_listing_models_is_open_to_viewers(client: TestClient) -> None:
    assert client.get("/api/v1/inference/models", headers=auth("viewer")).status_code == 200


# --------------------------------------------------------------------------- #
# Request validation                                                           #
# --------------------------------------------------------------------------- #


def test_an_unknown_field_is_refused(client: TestClient) -> None:
    """extra="forbid". P2 and P5 generate clients against this schema; a
    misspelled field that silently gets default behaviour is a bug found at demo
    time."""
    response = client.post(
        "/api/v1/inference/analyses",
        json={"scene": SCENE, "scene_href": "scene.tif", "modle": "typo"},
        headers=auth(),
    )
    assert response.status_code == 422


def test_a_missing_scene_reference_is_refused(client: TestClient) -> None:
    """No SceneRef means no provenance, and a Measurement cannot be built without
    it — better to refuse at the boundary than to fail deep in the pipeline."""
    response = client.post(
        "/api/v1/inference/analyses",
        json={"scene_href": "scene.tif"},
        headers=auth(),
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Analysis                                                                     #
# --------------------------------------------------------------------------- #


def test_a_real_scene_produces_a_measured_analysis(client: TestClient) -> None:
    """End to end: GeoTIFF on disk to a hectare figure with provenance."""
    response = client.post(
        "/api/v1/inference/analyses",
        json={"scene": SCENE, "scene_href": "scene.tif"},
        headers=auth(),
    )
    assert response.status_code == 200
    body = response.json()

    assert body["outcome"] == "analysed"
    measurement = body["measurements"][0]
    assert measurement["unit"] == "ha"
    assert float(measurement["value"]) > 0
    assert measurement["crs"] == "EPSG:32643"
    assert measurement["produced_by"] == "ml.geo.area.area_hectares"
    assert measurement["code_version"] == "test"
    assert measurement["derived_from"][0]["item_id"] == "India_1050276"


def test_with_no_model_registered_the_result_says_it_is_degraded(
    client: TestClient,
) -> None:
    """ADR-0007 D7: falling back to the baseline is legitimate *because it is
    labelled*. An unlabelled fallback is a number pretending to be something it
    is not."""
    body = client.post(
        "/api/v1/inference/analyses",
        json={"scene": SCENE, "scene_href": "scene.tif"},
        headers=auth(),
    ).json()

    assert body["degraded_from"] is not None
    assert any("degraded" in c for c in body["caveats"])


def test_the_baseline_can_be_requested_explicitly_without_being_degraded(
    client: TestClient,
) -> None:
    """Asking for the baseline is legitimate — it is the comparison every claim is
    measured against — so it is not reported as degradation."""
    body = client.post(
        "/api/v1/inference/analyses",
        json={"scene": SCENE, "scene_href": "scene.tif", "model": "baseline"},
        headers=auth(),
    ).json()

    assert body["outcome"] == "analysed"
    assert body["degraded_from"] is None


def test_confidence_is_never_a_bare_number(client: TestClient) -> None:
    """D5: a confidence must declare its basis. There is no calibration report
    yet, so the only honest basis is NOT_CALIBRATED and the value must be null."""
    body = client.post(
        "/api/v1/inference/analyses",
        json={"scene": SCENE, "scene_href": "scene.tif"},
        headers=auth(),
    ).json()

    assert body["confidence"]["basis"] == "not_calibrated"
    assert body["confidence"]["value"] is None


# --------------------------------------------------------------------------- #
# Abstention                                                                   #
# --------------------------------------------------------------------------- #


def test_a_missing_raster_abstains_with_200_not_500(client: TestClient) -> None:
    """An abstention is a successful answer to "can you measure this?".

    Returning 5xx would make the caller treat a correct, considered refusal as a
    transport failure and retry it — which would burn the retry budget on a
    request that will never succeed.
    """
    response = client.post(
        "/api/v1/inference/analyses",
        json={"scene": SCENE, "scene_href": "absent.tif"},
        headers=auth(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "abstained"
    assert body["reason"] == "input_failed_preflight"
    assert "absent.tif" in body["explanation"]


def test_a_flat_scene_abstains_rather_than_inventing_a_threshold(
    client: TestClient, tmp_path: Path
) -> None:
    path = tmp_path / "flat.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=64,
        width=64,
        count=2,
        dtype="float32",
        crs="EPSG:32643",
        transform=from_origin(500000.0, 1000000.0, 10.0, 10.0),
    ) as sink:
        sink.write(np.full((2, 64, 64), -10.0, dtype=np.float32))
        sink.set_band_description(1, "VV")
        sink.set_band_description(2, "VH")

    body = client.post(
        "/api/v1/inference/analyses",
        json={"scene": SCENE, "scene_href": "flat.tif"},
        headers=auth(),
    ).json()

    assert body["outcome"] == "abstained"
    assert body["reason"] == "no_separable_threshold"


def test_both_outcomes_serialise_through_the_discriminated_union(
    client: TestClient,
) -> None:
    """The union is what P5 generates its client from, so both arms must round-trip.

    A response model that validates in Python but serialises one arm wrong is
    precisely the defect that only shows up at integration.
    """
    ok = client.post(
        "/api/v1/inference/analyses",
        json={"scene": SCENE, "scene_href": "scene.tif"},
        headers=auth(),
    ).json()
    no = client.post(
        "/api/v1/inference/analyses",
        json={"scene": SCENE, "scene_href": "absent.tif"},
        headers=auth(),
    ).json()

    assert ok["outcome"] == "analysed" and "measurements" in ok
    assert no["outcome"] == "abstained" and "reason" in no
    assert "measurements" not in no


# --------------------------------------------------------------------------- #
# Path containment                                                             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("href", ["../../../etc/passwd", "/etc/passwd"])
def test_a_path_escaping_the_data_root_is_refused(tmp_path: Path, href: str) -> None:
    """Checked after resolve(), so symlinks and .. are already collapsed.

    Comparing the string first is the classic mistake: "data/../../etc/passwd"
    starts with the root right up until it does not.
    """
    source = LocalRasterSource(tmp_path)
    with pytest.raises(PreflightError, match="outside|no raster"):
        source.resolve(href)


def test_a_remote_scheme_is_refused_with_an_explanation(tmp_path: Path) -> None:
    """This deployment reads local rasters only. The message names the reason and
    the issue, so the caller is not left guessing whether it is a bug."""
    with pytest.raises(PreflightError, match="local rasters"):
        LocalRasterSource(tmp_path).resolve("https://example.com/x.tif")


# --------------------------------------------------------------------------- #
# Model registry                                                               #
# --------------------------------------------------------------------------- #


def test_an_empty_registry_is_a_valid_answer(client: TestClient) -> None:
    body = client.get("/api/v1/inference/models", headers=auth("viewer")).json()
    assert body["models"] == []
    assert body["default"] is None


def test_a_model_that_loses_to_the_baseline_is_never_the_default(tmp_path: Path) -> None:
    """Serving it automatically would mean the service quietly does worse than the
    method it was meant to improve on. It stays listed and callable by name,
    because comparing the two is the entire point."""
    import json

    (tmp_path / "loser").mkdir(parents=True)
    (tmp_path / "loser" / "best.pt").write_bytes(b"not-a-real-checkpoint")
    (tmp_path / "loser" / "metrics.json").write_text(
        json.dumps(
            {
                "model": {"iou": 0.20, "f1": 0.30},
                "baseline": {"iou": 0.25, "f1": 0.33},
                "epochs": 20,
                "seed": 0,
                "parameters": 486481,
                "train_regions": ["Ghana"],
                "validation_regions": ["India"],
            }
        )
    )

    registry = ModelRegistry(tmp_path)
    (card,) = registry.cards()
    assert card.beats_baseline is False
    assert registry.default() is None


def test_a_model_without_metrics_reports_unknown_rather_than_assuming(
    tmp_path: Path,
) -> None:
    """ "We did not measure" and "it lost" are different claims. Collapsing them is
    how an unmeasured model gets described as a failed one, or the reverse."""
    (tmp_path / "unmeasured").mkdir(parents=True)
    (tmp_path / "unmeasured" / "best.pt").write_bytes(b"x")

    (card,) = ModelRegistry(tmp_path).cards()
    assert card.validation_iou is None
    assert card.beats_baseline is None


def test_an_unloadable_checkpoint_degrades_rather_than_failing(tmp_path: Path) -> None:
    (tmp_path / "broken").mkdir(parents=True)
    (tmp_path / "broken" / "best.pt").write_bytes(b"corrupt")
    (tmp_path / "broken" / "metrics.json").write_text('{"epochs": 1, "seed": 0}')

    with pytest.raises(ModelUnavailable):
        ModelRegistry(tmp_path).load("broken")


def test_requesting_an_unregistered_model_degrades_and_says_so(
    client: TestClient,
) -> None:
    body = client.post(
        "/api/v1/inference/analyses",
        json={"scene": SCENE, "scene_href": "scene.tif", "model": "does-not-exist"},
        headers=auth(),
    ).json()

    assert body["outcome"] == "analysed"
    assert body["degraded_from"] == "does-not-exist"
    assert any("does-not-exist" in c for c in body["caveats"])
