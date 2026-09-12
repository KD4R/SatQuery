"""
packages/observability/__init__.py

Centralised telemetry and logging setup.
"""

from .agent_metrics import AgentMetrics, get_agent_metrics
from .logging import setup_logging
from .telemetry import setup_telemetry

__all__ = ["AgentMetrics", "get_agent_metrics", "setup_logging", "setup_telemetry"]
