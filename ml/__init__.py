"""SatQuery ML -- P3 inference and machine-learning subsystem.

Owns the models that turn analysis-ready satellite rasters into masks,
measurements and the evidence about how well those measurements hold up. Does
not own how the rasters are produced (P4) or how the answer is narrated (P2).

Two rules run through every module here, enforced by types and tests rather
than by convention:

1. Every user-visible number is a ``Measurement`` carrying the function that
   produced it, the code version, the CRS it was measured in, and the scenes it
   derives from. No field has a default, so a bare float cannot be returned.

2. Absence of an answer is an ``Abstention`` -- a value, not an exception and
   not a placeholder. No code path in this package fabricates a result.

See ``ml/README.md`` and ``docs/adr/ADR-0007-ml-inference-foundation.md``.
"""

#: Recorded in every ``Measurement.code_version`` so a figure in an old report
#: can be traced to the code that produced it.
__version__ = "0.1.0"

__all__ = ["__version__"]
