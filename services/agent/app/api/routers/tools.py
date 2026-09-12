"""
services/agent/app/api/routers/tools.py — Tool registry inspection router (P2-05).
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from packages.auth.dependencies import get_current_user
from packages.auth.models import AuthContext
from services.agent.tools.registry import get_tool_registry

router = APIRouter(prefix="/api/v1/agent", tags=["agent-tools"])


@router.get("/tools", response_model=List[Dict[str, Any]])
async def list_tools(_: AuthContext = Depends(get_current_user)) -> List[Dict[str, Any]]:
    registry = get_tool_registry()
    return registry.list_tools()
