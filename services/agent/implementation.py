"""
services/agent/implementation.py — Agent FastAPI entrypoint re-export.
"""

from services.agent.app.api.implementation import app

__all__ = ["app"]
