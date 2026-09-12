"""Request-boundary validation for the inference service.

Split out of ``ml/preflight/`` at review (PR #17). The division is not arbitrary:

  * An **asset href** is an untrusted resource request arriving from another
    service. Deciding whether to dereference it is an access-control decision, and
    access control belongs at the service boundary -- which is here.

  * A **pixel array** that has already been read is a data-quality question, not a
    trust question. Those checks stayed in ``ml/io/preflight.py``, beside the
    reader that produces the arrays, because the analysis library needs them and
    must not import from ``services/`` -- the layering runs
    ``services -> ml -> packages``, never back up.

Note that the check here is on the *declared* href only. A permitted host can
redirect to a forbidden one, so the fetch layer must re-validate after every
redirect rather than trusting this call alone. That gap is tracked in issue #13,
along with merging this allowlist with the one in ``packages/geo/validation.py``.
"""

from __future__ import annotations

from urllib.parse import urlparse

from ml.io.preflight import PreflightError

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
#:
#: ``s3`` was listed here originally and has been removed, because it never worked:
#: in an ``s3://bucket/key`` URL the bucket occupies the host position, so the host
#: check compared a bucket name against a set of HTTPS hostnames and rejected every
#: such URL. An advertised capability that always fails is worse than an absent one
#: -- it invites a caller to build against it. Supporting S3 properly means a
#: separate bucket allowlist and a different validation path; until a provider
#: actually requires it, HTTPS endpoints cover every source in DEFAULT_ALLOWED_HOSTS.
ALLOWED_SCHEMES: frozenset[str] = frozenset({"https"})


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
