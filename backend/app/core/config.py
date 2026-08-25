"""Application settings, loaded from environment variables via Pydantic.

No secrets, hosts, or credentials are hardcoded — everything comes from the environment
(see ``.env.example`` for the full list). Non-secret constants (API base URL, rate limits)
carry documented defaults that the environment can override.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    environment: str = "dev"
    api_v1_prefix: str = "/api/v1"

    # Required — supplied by the environment, never defaulted (no hardcoded creds/hosts).
    database_url: str = Field(..., description="Async DSN, e.g. postgresql+asyncpg://...")
    redis_url: str = Field(..., description="e.g. redis://localhost:6379/0")
    balldontlie_api_key: str = Field(..., description="balldontlie.io Free-tier API key")

    # Non-secret, documented defaults (overridable via env).
    balldontlie_base_url: str = "https://api.balldontlie.io/v1"
    provider_rate_limit_per_min: int = 5
    api_rate_limit_per_min: int = 60
    # Comma-separated allowed CORS origins (frontend URLs). Same-origin deploys can leave this.
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (env is read once per process)."""
    return Settings()  # values come from the environment
