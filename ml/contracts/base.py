"""Base model for every contract object in the P3 inference subsystem.

Design rule
-----------
Contracts are the spine of this subsystem. Two consumers (P2 evidence assembly and
P4 geometry handling) and one producer (P4 asset discovery) bind to these shapes,
so they are deliberately hostile to accidental change:

``extra="forbid"``
    An unexpected field is an error, not silently dropped. If P4 starts sending a
    new field we find out immediately instead of ignoring data we should handle.

``frozen=True``
    Contract objects are immutable once constructed. A ``Measurement`` that could be
    mutated after validation would defeat the point of validating it -- provenance
    could be attached and then quietly replaced.

``validate_assignment=True``
    Belt and braces alongside ``frozen``; if a subclass ever unfreezes, assignment
    is still validated.

``str_strip_whitespace=True``
    Identifiers arriving from STAC responses routinely carry trailing whitespace.

No field in any contract below has a default value unless the default is genuinely
the only correct value. This is intentional: a default is how provenance goes
missing. The constructor should be impossible to satisfy without supplying the
information that makes the object trustworthy.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Strict(BaseModel):
    """Immutable, whitelist-validated base for all contract objects."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
        str_strip_whitespace=True,
        # Re-validate nested models even when they arrive already constructed.
        # Without this, a model built before a validator was tightened could slip
        # through when nested inside a newer parent.
        revalidate_instances="always",
    )
