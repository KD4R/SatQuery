"""Preflight validation: assert the input is what it claims to be, before processing.

Issue P3-02. This is the gate that turns "we assumed the data was in dB" into a
typed failure at the boundary rather than a wrong number at the end.

Design note on the return type
------------------------------
Failures here do not raise past the service boundary -- they become an
:class:`~ml.contracts.outcome.Abstention` with reason
``INPUT_FAILED_PREFLIGHT``. Internally a :class:`PreflightError` is raised so that
the offending check is easy to locate, and the caller translates. That keeps the
"absence of an answer is a value, not an exception" rule at the API surface while
keeping tracebacks useful inside the package.

Also owned here (P3's genuine share of the section 8 security table): the SSRF
allowlist. An asset ``href`` arriving from an upstream service is an untrusted
resource request. It is checked against a host allowlist *before* anything
dereferences it. Note that the check in this module is on the declared href only;
the fetch layer must re-check after any redirect, because a permitted host can
redirect to a forbidden one.
"""

from __future__ import annotations

from urllib.parse import urlparse

import numpy as np
import numpy.typing as npt

from ml.contracts.scene import RasterSpec

#: Hosts P3 is permitted to dereference asset URLs from.
#:
#: Deliberately a closed list. Adding a provider is a reviewed change, which is the
#: point -- an SSRF control that anyone can widen by accident is not a control.
#: These correspond to the providers evaluated in the P3 plan:
#:   - ASF HyP3 / NASA Earthdata (recommended primary for live SAR)
#:   - Copernicus Data Space Ecosystem (secondary catalogue)
#:   - Bhoonidhi / NRSC (India-native, owned by P4)
DEFAULT_ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "sentinel1.asf.alaska.edu",
        "datapool.asf.alaska.edu",
        "hyp3-api.asf.alaska.edu",
        "cumulus.asf.alaska.edu",
        "zipper.dataspace.copernicus.eu",
        "download.dataspace.copernicus.eu",
        "stac.dataspace.copernicus.eu",
        "bhoonidhi-api.nrsc.gov.in",
    }
)

#: Only these URL schemes may be dereferenced. ``file://`` is excluded on purpose:
#: an attacker-supplied ``file:///etc/passwd`` is the textbook SSRF escalation.
ALLOWED_SCHEMES: frozenset[str] = frozenset({"https", "s3"})


class PreflightError(ValueError):
    """An input failed validation and must not be processed."""


def validate_href(href: str, *, allowed_hosts: frozenset[str] | None = None) -> None:
    """Reject an asset URL that P3 is not permitted to fetch.

    Parameters
    ----------
    href
        The URL as supplied by the upstream service.
    allowed_hosts
        Override for the default allowlist. Tests use this; production should not.

    Raises
    ------
    PreflightError
        If the scheme is not permitted, the host is missing, or the host is not on
        the allowlist.
    """
    hosts = DEFAULT_ALLOWED_HOSTS if allowed_hosts is None else allowed_hosts

    parsed = urlparse(href)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise PreflightError(
            f"scheme {parsed.scheme!r} is not permitted (allowed: " f"{sorted(ALLOWED_SCHEMES)})"
        )
    if not parsed.hostname:
        raise PreflightError(f"asset href has no host: {href!r}")
    if parsed.hostname.lower() not in hosts:
        raise PreflightError(
            f"host {parsed.hostname!r} is not on the provider allowlist. "
            "Adding a provider is a reviewed change to DEFAULT_ALLOWED_HOSTS."
        )


def validate_against_spec(
    array: npt.NDArray[np.floating],
    actual: RasterSpec,
    expected: RasterSpec,
) -> None:
    """Assert that a loaded array matches both its own declared spec and what we need.

    Two comparisons happen here and they are different:

    1. ``array`` versus ``actual`` -- does the data match what the provider *said*
       it was? A mismatch means the metadata is wrong, which invalidates everything
       downstream including the scale declaration.
    2. ``actual`` versus ``expected`` -- is what the provider gave us what this
       model needs? A mismatch here is recoverable (reorder bands, convert scale);
       this function reports it rather than silently fixing it, so the conversion
       is an explicit, logged step.

    Raises
    ------
    PreflightError
        On any mismatch, with a message naming the specific field.
    """
    # --- 1. Data versus its own declared metadata -------------------------------
    expected_bands = len(actual.band_order)
    if array.ndim != 3:
        raise PreflightError(f"expected a 3-D (band, y, x) array, got shape {array.shape}")
    if array.shape[0] != expected_bands:
        raise PreflightError(
            f"declared band_order has {expected_bands} bands "
            f"{tuple(b.value for b in actual.band_order)} but array has "
            f"{array.shape[0]}"
        )
    if array.shape[1] != actual.height or array.shape[2] != actual.width:
        raise PreflightError(
            f"declared dimensions {actual.width}x{actual.height} do not match array "
            f"shape {array.shape[2]}x{array.shape[1]}"
        )
    if array.dtype.name != actual.dtype:
        raise PreflightError(
            f"declared dtype {actual.dtype!r} does not match array dtype " f"{array.dtype.name!r}"
        )

    # --- 2. Declared metadata versus what the model needs -----------------------
    if actual.band_order != expected.band_order:
        raise PreflightError(
            "band order mismatch: source provides "
            f"{tuple(b.value for b in actual.band_order)} but the model expects "
            f"{tuple(b.value for b in expected.band_order)}. Reorder explicitly; "
            "silently mismatching them normalises each channel with the other "
            "channel's statistics, which produces a plausible wrong answer rather "
            "than an error."
        )
    if actual.crs != expected.crs:
        raise PreflightError(f"CRS mismatch: source is {actual.crs}, model expects {expected.crs}")
    # Scale is intentionally *not* required to match: converting is legitimate and
    # is handled by ensure_decibel(). It is checked for being a known value only.
    if actual.scale is None:  # pragma: no cover - pydantic makes this unreachable
        raise PreflightError("source raster does not declare a backscatter scale")


def validate_finite_fraction(
    array: npt.NDArray[np.floating],
    *,
    minimum: float = 0.5,
) -> float:
    """Reject a raster that is mostly no-data, and report the valid fraction.

    A chip that is 90% no-data can still produce a mask and an area figure, and
    that figure will be confidently wrong because it describes a sliver of the AOI
    as though it described the whole thing.

    Returns
    -------
    float
        The fraction of finite samples, so the caller can record it as a caveat
        even when it passes.
    """
    if array.size == 0:
        raise PreflightError("raster is empty")
    fraction = float(np.count_nonzero(np.isfinite(array)) / array.size)
    if fraction < minimum:
        raise PreflightError(
            f"only {fraction:.1%} of samples are finite (minimum {minimum:.0%}); "
            "an area measured from this would describe a fraction of the AOI as "
            "though it described all of it"
        )
    return fraction
