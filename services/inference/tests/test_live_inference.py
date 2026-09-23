"""P3 inference work pack: live model, verified weights, honest confidence, outputs.

Written to run in CI, which installs requirements.txt and not torch. Everything
here that can be checked without a deep-learning stack is -- the checksum logic,
the confidence rules, the output artefacts, the storage sink, the fetcher. The one
test that needs the real model skips cleanly when torch or the weights are absent,
and says which.

Each test names the defect or promise it defends, because every one of these was
either false before this change or promised in a README and not implemented.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from packages.contracts import ConfidenceBasis
from services.inference.artifacts import ArtifactWriteError, LocalArtifactSink
from services.inference.confidence import confidence_for
from services.inference.outputs import mask_geojson, mask_geotiff
from services.inference.registry import ModelCard, ModelRegistry, ModelUnavailable

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]


# ── fixtures ─────────────────────────────────────────────────────────────────


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def model_tree(tmp_path: Path) -> tuple[Path, Path]:
    """A registry root and a manifest root holding one model with a real manifest.

    The "checkpoint" is arbitrary bytes. Verification is a property of the file,
    not of what is inside it, so these tests need no torch and no real weights.
    """
    models, manifests = tmp_path / "models", tmp_path / "manifests"
    model = models / "demo"
    model.mkdir(parents=True)
    (model / "best.pt").write_bytes(b"not-a-real-checkpoint" * 100)
    (model / "metrics.json").write_text(
        json.dumps({"epochs": 3, "seed": 0, "model": {"iou": 0.4}, "baseline": {"iou": 0.2}})
    )
    (manifests / "demo").mkdir(parents=True)
    (manifests / "demo" / "manifest.json").write_text(
        json.dumps({"artifact": {"file": "best.pt", "sha256": _sha(model / "best.pt")}})
    )
    return models, manifests


def _card(**overrides: Any) -> ModelCard:
    base = ModelCard(
        name="demo",
        version="e1-s0",
        checkpoint=Path("best.pt"),
        parameters=1,
        validation_iou=0.4,
        validation_f1=0.5,
        validation_regions=("India",),
        train_regions=("Spain",),
        baseline_iou=0.2,
        stratified_iou={},
    )
    return replace(base, **overrides)


# ── task 1: weights are verified before they are deserialised ────────────────


def test_matching_checkpoint_verifies(model_tree: tuple[Path, Path]) -> None:
    models, manifests = model_tree
    registry = ModelRegistry(root=models, manifest_root=manifests)
    card = registry.cards()[0]
    assert registry._verify(card) is True


@pytest.mark.parametrize(
    "damage",
    [
        pytest.param(lambda b: b[:-64], id="truncated"),
        pytest.param(lambda b: b[:10] + bytes([b[10] ^ 0xFF]) + b[11:], id="one-byte-flipped"),
        pytest.param(lambda b: b + b"x", id="appended"),
    ],
)
def test_damaged_checkpoint_is_refused_before_torch_is_touched(
    model_tree: tuple[Path, Path], damage
) -> None:
    """infrastructure/models/README.md promised "a tampered or truncated download
    is detected". Nothing detected it: the registry loaded whatever best.pt was on
    disk.

    The assertion on the message is the point. load() imports torch *after*
    verifying; on a CI runner with no torch, a test that only checked for
    ModelUnavailable would pass for the wrong reason -- "torch is not installed" --
    and prove nothing about the checksum. Matching "does not match its manifest"
    proves verification ran first.
    """
    models, manifests = model_tree
    checkpoint = models / "demo" / "best.pt"
    checkpoint.write_bytes(damage(checkpoint.read_bytes()))

    registry = ModelRegistry(root=models, manifest_root=manifests)
    with pytest.raises(ModelUnavailable, match="does not match its manifest"):
        registry.load("demo")


def test_missing_manifest_is_refused_when_required(model_tree: tuple[Path, Path]) -> None:
    models, _ = model_tree
    registry = ModelRegistry(root=models, manifest_root=models / "nowhere", require_manifest=True)
    with pytest.raises(ModelUnavailable, match="no manifest"):
        registry.load("demo")


def test_missing_manifest_is_allowed_but_marked_when_not_required(
    model_tree: tuple[Path, Path],
) -> None:
    """A freshly trained model can be tried locally before its manifest exists --
    but the card records that it was unverified, and the analysis says so."""
    models, _ = model_tree
    registry = ModelRegistry(root=models, manifest_root=models / "nowhere", require_manifest=False)
    assert registry._verify(registry.cards()[0]) is False


def test_malformed_manifest_is_refused(model_tree: tuple[Path, Path]) -> None:
    models, manifests = model_tree
    (manifests / "demo" / "manifest.json").write_text("{ not json")
    registry = ModelRegistry(root=models, manifest_root=manifests)
    with pytest.raises(ModelUnavailable, match="unreadable"):
        registry.load("demo")


def test_committed_manifest_matches_the_shape_the_registry_reads() -> None:
    """The manifest in the repo must be one _verify() can use. A manifest nobody
    can parse would make SATQUERY_REQUIRE_MANIFEST refuse the production model."""
    manifest = json.loads(
        (REPO_ROOT / "infrastructure/models/hand-only-v2/manifest.json").read_text()
    )
    sha = manifest["artifact"]["sha256"]
    assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)
    assert manifest["artifact"]["uri"].endswith(f"/{sha}/best.pt"), (
        "the object key must contain the digest, so a new checkpoint can never "
        "overwrite the one an existing manifest points at"
    )
    assert set(manifest["sidecars"]) == {"metrics.json", "calibration.json"}


# ── task 3: confidence says what calibration actually found ──────────────────


PROBABILITY = np.array([[0.9, 0.8], [0.3, 0.1]], dtype=np.float32)
MASK = PROBABILITY >= 0.5


def test_unmeasured_calibration_reports_no_value() -> None:
    confidence = confidence_for(_card(), PROBABILITY, MASK)
    assert confidence.basis is ConfidenceBasis.NOT_CALIBRATED
    assert confidence.value is None
    assert "has not been measured" in confidence.caveats[0]


def test_failed_calibration_reports_no_value_and_says_why() -> None:
    """The state hand-only-v2 is actually in: measured, ECE 0.0583, bar 0.05.

    Before this, every analysis carried "model output is uncalibrated; see P3-11"
    -- written before P3-11 ran. P3-11 then measured the model and found it short,
    and the caveat went on claiming no calibration existed.
    """
    card = _card(
        calibration_ece=0.0583,
        calibration_passes=False,
        calibration_bar=0.05,
        calibration_temperature=0.7486,
        calibration_report="reports/calibration.md",
    )
    confidence = confidence_for(card, PROBABILITY, MASK)

    assert confidence.basis is ConfidenceBasis.NOT_CALIBRATED
    assert confidence.value is None, "a failed calibration must not print a number"
    joined = " ".join(confidence.caveats)
    assert "0.0583" in joined and "0.05" in joined
    assert "reports/calibration.md" in joined
    assert "P3-11" not in joined, "the stale caveat must be gone"


def test_passing_calibration_reports_the_temperature_scaled_mean() -> None:
    card = _card(
        calibration_ece=0.03,
        calibration_passes=True,
        calibration_bar=0.05,
        calibration_temperature=2.0,
        calibration_report="reports/calibration.md",
    )
    confidence = confidence_for(card, PROBABILITY, MASK)

    assert confidence.basis is ConfidenceBasis.CALIBRATED_PROBABILITY
    assert confidence.calibration_ref == "reports/calibration.md"
    # Recompute independently: logit, divide by T, sigmoid, mean over called water.
    called = PROBABILITY[MASK].astype(np.float64)
    logits = np.log(called / (1 - called)) / 2.0
    expected = float(np.mean(1 / (1 + np.exp(-logits))))
    assert confidence.value == Decimal(str(round(expected, 4)))
    # T > 1 softens an overconfident model: the calibrated mean must sit below the raw.
    assert float(confidence.value) < float(called.mean())


def test_passing_calibration_without_a_temperature_refuses_to_guess() -> None:
    card = _card(calibration_ece=0.03, calibration_passes=True, calibration_temperature=None)
    confidence = confidence_for(card, PROBABILITY, MASK)
    assert confidence.basis is ConfidenceBasis.NOT_CALIBRATED
    assert confidence.value is None


def test_calibration_never_changes_which_pixels_are_water() -> None:
    """The threshold is 0.5, which is logit 0, which temperature scaling leaves at
    0. If that ever stopped being true, calibrating the model would silently change
    the reported area. Asserted over a range of temperatures, not assumed."""
    from ml.evaluation.calibration import apply_temperature

    rng = np.random.default_rng(0)
    probability = rng.uniform(0.001, 0.999, size=(64, 64))
    logits = np.log(probability / (1 - probability))
    raw_mask = probability >= 0.5
    for temperature in (0.25, 0.7486, 1.0, 1.5, 4.0):
        assert np.array_equal(apply_temperature(logits, temperature) >= 0.5, raw_mask)


# ── task 2: the mask and its polygons are kept, and agree with the area ──────


def _synthetic_mask() -> tuple[np.ndarray, object, str, float]:
    """Two blobs, one joined to a third only diagonally, on a 10 m UTM grid."""
    mask = np.zeros((40, 40), dtype=bool)
    mask[5:15, 5:15] = True  # 100 px
    mask[20:30, 20:28] = True  # 80 px
    mask[30, 28] = True  # joins the second blob diagonally only
    transform = from_origin(500_000, 3_000_000, 10, 10)
    return mask, transform, "EPSG:32646", 100.0


def test_geotiff_round_trips_the_exact_mask() -> None:
    mask, transform, crs, _ = _synthetic_mask()
    raw = mask_geotiff(mask, transform=transform, crs=crs)
    with rasterio.MemoryFile(raw) as memfile, memfile.open() as dataset:
        assert dataset.crs.to_string() == crs
        assert dataset.transform == transform
        assert np.array_equal(dataset.read(1) == 1, mask)


def test_geojson_areas_sum_to_the_measured_area() -> None:
    """The invariant outputs.py exists to keep: the polygons on the map must add
    up to the hectares in the report. Also catches the 4- vs 8-connectivity bug --
    rasterio.features.shapes defaults to 4, which would split the diagonally joined
    blob and stamp the whole component's area on each piece."""
    mask, transform, crs, pixel_area = _synthetic_mask()
    collection = json.loads(
        mask_geojson(mask, transform=transform, crs=crs, pixel_area_m2=pixel_area)
    )
    total_ha = sum(f["properties"]["area_ha"] for f in collection["features"])
    assert total_ha == pytest.approx(mask.sum() * pixel_area / 10_000)
    assert len(collection["features"]) == 2, "8-connected: the diagonal pixel joins its blob"


def test_geojson_is_wgs84() -> None:
    """RFC 7946 requires WGS84; a browser map assumes it. UTM metres rendered as
    degrees would put the flood somewhere in the ocean."""
    mask, transform, crs, pixel_area = _synthetic_mask()
    collection = json.loads(
        mask_geojson(mask, transform=transform, crs=crs, pixel_area_m2=pixel_area)
    )
    for feature in collection["features"]:
        for ring in feature["geometry"]["coordinates"]:
            for lon, lat in ring:
                assert -180 <= lon <= 180 and -90 <= lat <= 90


def test_empty_mask_gives_an_empty_collection() -> None:
    mask = np.zeros((10, 10), dtype=bool)
    collection = json.loads(
        mask_geojson(mask, transform=from_origin(0, 0, 10, 10), crs="EPSG:32646", pixel_area_m2=100)
    )
    assert collection["features"] == []


@pytest.mark.parametrize("key", ["../escape.tif", "/abs/path.tif", "a/../../b.tif", "a\\b.tif", ""])
def test_artifact_sink_refuses_keys_that_escape_its_root(tmp_path: Path, key: str) -> None:
    sink = LocalArtifactSink(tmp_path / "store")
    with pytest.raises(ArtifactWriteError):
        sink.put(key, b"x", "application/octet-stream")
    assert not (tmp_path / "escape.tif").exists()


def test_artifact_sink_writes_under_its_root(tmp_path: Path) -> None:
    sink = LocalArtifactSink(tmp_path)
    ref = sink.put("analyses/abc/water_mask.tif", b"data", "image/tiff")
    assert ref == "analyses/abc/water_mask.tif"
    assert (tmp_path / ref).read_bytes() == b"data"


# ── task 1: weights are fetched by checksum ──────────────────────────────────


def test_fetch_installs_only_after_every_file_verifies(tmp_path: Path) -> None:
    """A tampered sidecar must stop the whole install -- including the checkpoint,
    which had already verified. Otherwise a half-installed model with a real
    checkpoint and an edited metrics file would be served."""
    from ml.scripts.fetch_model import FetchError, fetch

    source = tmp_path / "source" / "demo"
    source.mkdir(parents=True)
    (source / "best.pt").write_bytes(b"weights")
    (source / "metrics.json").write_text('{"model": {"iou": 0.4}}')
    manifests = tmp_path / "manifests" / "demo"
    manifests.mkdir(parents=True)
    (manifests / "manifest.json").write_text(
        json.dumps(
            {
                "artifact": {
                    "file": "best.pt",
                    "sha256": _sha(source / "best.pt"),
                    "uri": "s3://b/k",
                },
                "sidecars": {"metrics.json": _sha(source / "metrics.json")},
            }
        )
    )
    (source / "metrics.json").write_text('{"model": {"iou": 0.99}}')  # promote a worse model

    target = tmp_path / "models"
    with pytest.raises(FetchError, match="metrics.json"):
        fetch(
            "demo",
            manifest_root=tmp_path / "manifests",
            model_root=target,
            source_dir=tmp_path / "source",
        )
    assert not (target / "demo" / "best.pt").exists()


# ── schema: /models actually reports calibration ─────────────────────────────


def test_model_summary_keeps_every_card_field() -> None:
    """ModelCard grew calibration fields in P3-11, but ModelSummary never declared
    them, and pydantic's default extra="ignore" dropped them without a word. So
    /api/v1/inference/models has never reported calibration at all. This fails if
    a card field is ever added without its summary field."""
    from services.inference.schemas import ModelSummary

    card = _card(
        calibration_ece=0.0583,
        calibration_passes=False,
        calibration_bar=0.05,
        calibration_temperature=0.75,
        calibration_report="r.md",
        checksum_verified=True,
        in_channels=3,
        uses_permanent_water_prior=True,
        training_labelling="hand",
    )
    as_dict = card.to_dict()
    summary = ModelSummary(**as_dict).model_dump()
    dropped = sorted(set(as_dict) - set(summary))
    assert dropped == [], f"ModelSummary silently drops {dropped}"
    assert summary["calibration_ece"] == 0.0583


# ── the real model, when it is available ─────────────────────────────────────


def test_real_checkpoint_matches_its_committed_manifest() -> None:
    """Runs where the weights exist (a developer machine, the inference image);
    skips in CI, where they deliberately do not. No torch needed: it checks the
    file the registry would load against the manifest it would load it with."""
    checkpoint = REPO_ROOT / "artifacts/hand-only-v2/best.pt"
    if not checkpoint.is_file():
        pytest.skip("artifacts/hand-only-v2/best.pt not present (weights are not committed)")
    registry = ModelRegistry(
        root=REPO_ROOT / "artifacts",
        manifest_root=REPO_ROOT / "infrastructure/models",
        require_manifest=True,
    )
    card = next(c for c in registry.cards() if c.name == "hand-only-v2")
    assert registry._verify(card) is True


# ── the extent route: how the browser gets the polygons ──────────────────────


@pytest.fixture
def extent_client(tmp_path: Path):
    """The real app with a real local sink, no model needed."""
    from fastapi.testclient import TestClient

    from services.inference.dependencies import get_artifact_sink, get_registry
    from services.inference.implementation import app

    store = tmp_path / "store"
    sink = LocalArtifactSink(store)
    # An empty registry: the extent route must not need a model, and this keeps
    # the lifespan warm-up a no-op so the test runs without torch.
    app.dependency_overrides[get_registry] = lambda: ModelRegistry(tmp_path / "none")
    app.dependency_overrides[get_artifact_sink] = lambda: sink
    try:
        with TestClient(app) as client:
            yield client, sink
    finally:
        app.dependency_overrides.clear()


def _viewer() -> dict[str, str]:
    from services.inference.tests.test_api import auth

    return auth("viewer")


TRACE = "8f1bc78d-ad93-4942-bcf2-f3e8d499a429"


def test_extent_serves_the_stored_geojson(extent_client) -> None:
    client, sink = extent_client
    sink.put(
        f"analyses/{TRACE}/water_extent.geojson",
        b'{"type":"FeatureCollection","features":[]}',
        "application/geo+json",
    )

    response = client.get(f"/api/v1/inference/analyses/{TRACE}/extent", headers=_viewer())

    assert response.status_code == 200
    # geo+json, not application/json: the map consumes it directly.
    assert response.headers["content-type"].startswith("application/geo+json")
    assert response.json()["type"] == "FeatureCollection"


def test_extent_is_404_when_nothing_was_stored(extent_client) -> None:
    client, _ = extent_client
    response = client.get(f"/api/v1/inference/analyses/{TRACE}/extent", headers=_viewer())
    assert response.status_code == 404


def test_extent_requires_a_token(extent_client) -> None:
    client, _ = extent_client
    assert client.get(f"/api/v1/inference/analyses/{TRACE}/extent").status_code == 401


@pytest.mark.parametrize("bad", ["../../etc/passwd", "not-a-uuid", "..", "%2e%2e"])
def test_extent_refuses_anything_that_is_not_a_uuid(extent_client, bad: str) -> None:
    """The trace id becomes part of a storage key, so the route types it as a UUID
    and FastAPI rejects everything else before the handler runs. No caller-supplied
    string ever reaches the sink."""
    client, _ = extent_client
    response = client.get(f"/api/v1/inference/analyses/{bad}/extent", headers=_viewer())
    assert response.status_code in (404, 422), response.status_code


def test_extent_says_so_when_no_store_is_configured(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from services.inference.dependencies import get_artifact_sink, get_registry
    from services.inference.implementation import app

    app.dependency_overrides[get_registry] = lambda: ModelRegistry(tmp_path / "none")
    app.dependency_overrides[get_artifact_sink] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/inference/analyses/{TRACE}/extent", headers=_viewer())
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "NO_ARTIFACT_STORE"
    finally:
        app.dependency_overrides.clear()
