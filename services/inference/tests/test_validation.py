"""SSRF allowlist tests for the inference service boundary.

Moved out of ml/ at review (PR #17) to follow the code: deciding whether an
untrusted href may be dereferenced is an access-control decision and lives at the
service boundary, while the array checks stayed beside the reader in ml/io/.
"""

from __future__ import annotations

import pytest

from ml.io.preflight import PreflightError
from services.inference.validation import validate_href

# CI selects tests by marker (`pytest -m unit`); an unmarked test never runs.
pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "href",
    [
        "https://datapool.asf.alaska.edu/RTC/SA/x.tif",
        "https://zipper.dataspace.copernicus.eu/odata/v1/Products(1)/$value",
        "https://bhoonidhi-api.nrsc.gov.in/download?id=abc",
    ],
)
def test_allowlisted_providers_are_accepted(href: str) -> None:
    validate_href(href)  # must not raise


@pytest.mark.parametrize(
    "href",
    [
        "https://evil.example.com/payload.tif",
        "https://datapool.asf.alaska.edu.evil.example.com/x.tif",  # suffix attack
    ],
)
def test_non_allowlisted_hosts_are_refused(href: str) -> None:
    with pytest.raises(PreflightError, match="allowlist"):
        validate_href(href)


@pytest.mark.parametrize(
    "href",
    [
        "file:///etc/passwd",  # textbook SSRF escalation
        "http://datapool.asf.alaska.edu/x.tif",  # plaintext not permitted
        "gopher://datapool.asf.alaska.edu/x",
    ],
)
def test_disallowed_schemes_are_refused(href: str) -> None:
    with pytest.raises(PreflightError, match="scheme"):
        validate_href(href)


def test_href_without_host_is_refused() -> None:
    with pytest.raises(PreflightError, match="no host"):
        validate_href("https:///no-host-here.tif")
