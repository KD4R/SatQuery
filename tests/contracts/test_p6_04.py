"""
P6-04 -- Contract test harness and generated fixtures

Validates that canonical contracts from packages/contracts/ml.py
are correctly structured, reject invalid data, and produce
deterministic serialization.

Note: contracts/ml.py uses Python 3.10+ syntax (int | None).
These tests skip on Python < 3.10.
"""

import sys
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.contracts import (
    Abstention,
    AbstentionReason,
    Analysis,
    Confidence,
    ConfidenceBasis,
    Measurement,
    MeasurementUnit,
    MissionOutcome,
    PassDirection,
    Provider,
    SceneRef,
    Strict,
)

pytestmark = pytest.mark.contract

# Skip entire module on Python < 3.10
if sys.version_info < (3, 10):
    pytest.skip("contracts/ml.py requires Python 3.10+", allow_module_level=True)


# -- Fixture: Valid SceneRef --


@pytest.fixture
def valid_scene_ref():
    return SceneRef(
        provider=Provider.PLANETARY_COMPUTER,
        collection="sentinel-1-rtc",
        item_id="S1A_IW_GRDH_1SDV_20240918T120000",
        acquired_at=datetime(2024, 9, 18, 12, 0, 0),
        platform="sentinel-1a",
        instrument="c-sar",
        relative_orbit=42,
        pass_direction=PassDirection.DESCENDING,
        href=(
            "https://planetarycomputer.microsoft.com/api/stac/"
            "collections/sentinel-1-rtc/items/S1A_IW_GRDH"
        ),
        cloud_cover=None,
    )


@pytest.fixture
def valid_measurement(valid_scene_ref):
    return Measurement(
        name="flood_extent",
        value=Decimal("18.7"),
        unit=MeasurementUnit.HECTARES,
        produced_by="area_hectares",
        code_version="abc123",
        crs="EPSG:32644",
        derived_from=(valid_scene_ref,),
    )


# -- SceneRef Contract --


class TestSceneRefContract:
    def test_valid_construction(self, valid_scene_ref):
        assert valid_scene_ref.provider == Provider.PLANETARY_COMPUTER
        assert valid_scene_ref.item_id.startswith("S1A")

    def test_frozen(self, valid_scene_ref):
        with pytest.raises(ValidationError):
            valid_scene_ref.item_id = "changed"

    def test_extra_forbidden(self, valid_scene_ref):
        with pytest.raises(ValidationError):
            SceneRef(**valid_scene_ref.model_dump(), extra_field="nope")

    def test_cloud_cover_range(self, valid_scene_ref):
        data = valid_scene_ref.model_dump()
        data["cloud_cover"] = 150
        with pytest.raises(ValidationError):
            SceneRef(**data)

    def test_min_length_fields(self):
        with pytest.raises(ValidationError):
            SceneRef(
                provider=Provider.BHOONIDHI,
                collection="",
                item_id="test",
                acquired_at=datetime.now(),
                platform="test",
                instrument="test",
                relative_orbit=None,
                pass_direction=None,
                href="http://example.com",
            )

    def test_provider_is_enum(self):
        assert isinstance(Provider.BHOONIDHI, Provider)

    def test_all_providers_serializable(self):
        for p in Provider:
            dumped = p.value
            restored = Provider(dumped)
            assert restored == p


# -- Measurement Contract --


class TestMeasurementContract:
    def test_valid_construction(self, valid_measurement):
        assert valid_measurement.name == "flood_extent"
        assert valid_measurement.value == Decimal("18.7")

    def test_derived_from_must_not_be_empty(self, valid_scene_ref):
        with pytest.raises(ValidationError):
            Measurement(
                name="flood_extent",
                value=Decimal("18.7"),
                unit=MeasurementUnit.HECTARES,
                produced_by="area_hectares",
                code_version="abc123",
                crs="EPSG:32644",
                derived_from=(),
            )

    def test_measurement_is_strict(self, valid_measurement):
        assert issubclass(Measurement, Strict)


# -- Abstention Contract --


class TestAbstentionContract:
    def test_valid_construction(self):
        abstention = Abstention(
            reason=AbstentionReason.NO_SCENES_IN_WINDOW,
            explanation="No Sentinel-1 scenes found in the requested window.",
            nearest_usable=datetime(2024, 10, 1),
            scenes_seen=(),
            trace_id="trace-001",
        )
        assert abstention.outcome == "abstained"
        assert abstention.reason == AbstentionReason.NO_SCENES_IN_WINDOW

    def test_all_reasons_serializable(self):
        for r in AbstentionReason:
            dumped = r.value
            restored = AbstentionReason(dumped)
            assert restored == r


# -- Analysis Contract --


class TestAnalysisContract:
    def test_valid_construction(self, valid_measurement, valid_scene_ref):
        analysis = Analysis(
            measurements=(valid_measurement,),
            geometry_ref="geo-001",
            raster_refs=("s3://bucket/mask.tif",),
            confidence=None,
            scenes=(valid_scene_ref,),
            degraded_from=None,
            caveats=("4% radar shadow excluded",),
            trace_id="trace-002",
        )
        assert analysis.outcome == "analysed"
        assert len(analysis.measurements) == 1

    def test_measurements_must_not_be_empty(self, valid_scene_ref):
        with pytest.raises(ValidationError):
            Analysis(
                measurements=(),
                geometry_ref=None,
                raster_refs=(),
                confidence=None,
                scenes=(valid_scene_ref,),
                degraded_from=None,
                caveats=(),
                trace_id="trace-003",
            )


# -- MissionOutcome Discriminator --


class TestMissionOutcome:
    def test_analysis_is_valid_outcome(self, valid_measurement, valid_scene_ref):
        analysis = Analysis(
            measurements=(valid_measurement,),
            geometry_ref=None,
            raster_refs=(),
            confidence=None,
            scenes=(valid_scene_ref,),
            degraded_from=None,
            caveats=(),
            trace_id="trace-004",
        )
        assert analysis.outcome == "analysed"

    def test_abstention_is_valid_outcome(self):
        abstention = Abstention(
            reason=AbstentionReason.NO_SCENES_IN_WINDOW,
            explanation="No scenes",
            nearest_usable=None,
            scenes_seen=(),
            trace_id="trace-005",
        )
        assert abstention.outcome == "abstained"


# -- Confidence Contract --


class TestConfidenceContract:
    def test_model_agreement_basis(self):
        conf = Confidence(
            basis=ConfidenceBasis.MODEL_AGREEMENT,
            value=Decimal("0.91"),
            interval=None,
            calibration_ref=None,
            agreement_iou=Decimal("0.89"),
            caveats=("Radar shadow in 4% of AOI",),
        )
        assert conf.basis == ConfidenceBasis.MODEL_AGREEMENT

    def test_not_calibrated_has_no_value(self):
        conf = Confidence(
            basis=ConfidenceBasis.NOT_CALIBRATED,
            value=None,
            interval=None,
            calibration_ref=None,
            agreement_iou=None,
            caveats=(),
        )
        assert conf.value is None


# -- Schema Compatibility --


class TestP604SchemaCompatibility:
    def test_all_contracts_importable(self):
        assert SceneRef is not None
        assert Measurement is not None
        assert Analysis is not None
        assert Abstention is not None
        assert MissionOutcome is not None

    def test_json_roundtrip(self, valid_measurement, valid_scene_ref):
        analysis = Analysis(
            measurements=(valid_measurement,),
            geometry_ref="geo-001",
            raster_refs=("s3://bucket/mask.tif",),
            confidence=None,
            scenes=(valid_scene_ref,),
            degraded_from=None,
            caveats=(),
            trace_id="trace-010",
        )
        dumped = analysis.model_dump_json()
        restored = Analysis.model_validate_json(dumped)
        assert restored == analysis
