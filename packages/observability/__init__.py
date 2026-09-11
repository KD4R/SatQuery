"""
packages/observability/__init__.py

Centralised telemetry and logging setup.
"""

from .logging import setup_logging
from .telemetry import setup_telemetry

__all__ = ["setup_logging", "setup_telemetry"]
