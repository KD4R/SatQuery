"""
services/agent/config.py — Agent configuration from environment variables.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """
    All Agent settings resolved from environment variables.
    """
    openai_api_key: Optional[str] = None
    inference_service_url: str = "http://inference:8000"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

_settings: Optional[AgentSettings] = None

def get_agent_settings() -> AgentSettings:
    global _settings
    if _settings is None:
        _settings = AgentSettings()
    return _settings

def reset_agent_settings() -> None:
    global _settings
    _settings = None
