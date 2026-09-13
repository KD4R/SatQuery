"""Regression tests for defects found in review of the foundation commit.

Their shared property is what makes them worth keeping: **each one passed
silently before the fix.** Not one produced an exception, a warning or a visibly
odd value -- they produced plausible wrong numbers, which is the failure mode this
subsystem exists to prevent, and they got past a reviewer who had just written the
trap list.

Distributed from a single module into each package's own tests at review
(PR #17), to follow the repository's co-location convention.

Reference: https://github.com/KD4R/SatQuery/pull/17
"""

from __future__ import annotations


import numpy as np
import pytest

from ml.io.preflight import validate_finite_fraction
from services.inference.validation import ALLOWED_SCHEMES

pytestmark = pytest.mark.unit


def test_finite_nodata_sentinel_is_counted_as_invalid() -> None:
    """A raster that is 90% ``-9999`` reported 100% valid and passed the gate.

    GeoTIFF has no NaN convention for integer bands, so finite sentinels are
    ordinary, not exotic. Checking ``isfinite`` alone fails open on precisely the
    input this function exists to reject.
    """
    array = np.full((10, 10), -9999.0)
    array[:1, :] = -12.0  # 10% real observations

    assert validate_finite_fraction(array, minimum=0.5) == pytest.approx(1.0)

    with pytest.raises(ValueError, match="valid"):
        validate_finite_fraction(array, minimum=0.5, nodata=-9999.0)


def test_s3_is_no_longer_advertised() -> None:
    """It never worked: in ``s3://bucket/key`` the bucket sits in the host
    position, so the host check compared a bucket name against HTTPS hostnames and
    rejected every such URL. A capability that always fails is worse than an
    absent one, because a caller builds against it.
    """
    assert "s3" not in ALLOWED_SCHEMES
    assert ALLOWED_SCHEMES == frozenset({"https"})


def test_nan_nodata_still_works_when_a_sentinel_is_also_declared() -> None:
    array = np.full((10, 10), np.nan)
    array[:8, :] = -12.0
    assert validate_finite_fraction(array, minimum=0.5, nodata=-9999.0) == pytest.approx(0.8)
