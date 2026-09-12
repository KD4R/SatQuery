import logging
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class ProviderConfig(BaseSettings):
    """
    Configuration and secure secret boundary for EO Data Providers.
    Uses SecretStr to ensure credentials are masked in logs and stack traces.
    """

    bhoonidhi_username: SecretStr = Field(default=SecretStr(""), alias="BHOONIDHI_USERNAME")
    bhoonidhi_password: SecretStr = Field(default=SecretStr(""), alias="BHOONIDHI_PASSWORD")
    bhoonidhi_api_url: str = Field(
        default="https://bhoonidhi-api.nrsc.gov.in", alias="BHOONIDHI_API_URL"
    )

    # Redis configuration for token store and distributed locking
    redis_url: SecretStr = Field(default=SecretStr("redis://localhost:6379/0"), alias="REDIS_URL")

    # PostGIS connection string
    db_connection_string: SecretStr = Field(
        default=SecretStr("postgresql://user:pass@localhost:5432/satquery"), alias="DATABASE_URL"
    )

    # S3 / MinIO Configuration for Asset Staging
    s3_endpoint: str = Field(default="s3.amazonaws.com", alias="S3_ENDPOINT")
    s3_access_key: SecretStr = Field(default=SecretStr(""), alias="S3_ACCESS_KEY")
    s3_secret_key: SecretStr = Field(default=SecretStr(""), alias="S3_SECRET_KEY")
    s3_bucket: str = Field(default="satquery-assets", alias="S3_BUCKET")

    # Global timeout bounds for network resilience
    request_timeout_sec: float = Field(default=15.0, alias="REQUEST_TIMEOUT_SEC")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Global provider configuration singleton
config = ProviderConfig()


def mask_sensitive_url(url: str) -> str:
    """Utility to mask credentials in URLs before logging."""
    if "@" not in url:
        return url
    protocol_part, rest = url.split("://", 1)
    creds_part, host_part = rest.split("@", 1)
    return f"{protocol_part}://***:***@{host_part}"
