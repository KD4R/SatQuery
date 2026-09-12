"""Canonical cross-service contracts.

Authority: P1 (Tech Lead / Backend Architect).

Import from here, not from sub-modules directly, so that P1 can reorganise
the internals without breaking every import across the monorepo.

Usage::

    from packages.contracts import SceneRef, MissionOutcome, Analysis, Abstention
"""

from packages.contracts.ml import (  # noqa: F401
    Strict,
    Provider,
    PassDirection,
    SceneRef,
    Observation,
    MeasurementUnit,
    PHYSICAL_UNITS,
    ConfidenceBasis,
    Confidence,
    Measurement,
    AbstentionReason,
    Abstention,
    Analysis,
    MissionOutcome,
)
