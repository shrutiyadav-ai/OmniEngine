"""
OmniEngine — Application Configuration

Centralized configuration using Pydantic BaseSettings with environment
variable loading. All settings are validated at startup; missing required
values will prevent the application from starting.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    environment: Literal["development", "staging", "production", "testing"] = "development"
    app_name: str = "OmniEngine"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # API Security
    api_secret_key: str = "CHANGE_ME_TO_A_RANDOM_64_CHAR_HEX_STRING"  # noqa: S105
    api_keys: str = "dev-key-change-me-in-production"
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    # -------------------------------------------------------------------------
    # Database (PostgreSQL)
    # -------------------------------------------------------------------------
    database_url: str = "postgresql+asyncpg://omni:omni_dev_password@localhost:5432/omniengine"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_recycle: int = 3600
    db_echo: bool = False

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    redis_session_ttl: int = 86400  # 24 hours
    rate_limit_rpm: int = 60  # requests per minute

    # -------------------------------------------------------------------------
    # Qdrant Vector Database
    # -------------------------------------------------------------------------
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_collection_name: str = "omni_memories"
    qdrant_embedding_dim: int = 1536

    # -------------------------------------------------------------------------
    # LLM Provider API Keys
    # -------------------------------------------------------------------------
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_genai_api_key: str = ""

    # -------------------------------------------------------------------------
    # Model Router
    # -------------------------------------------------------------------------
    model_tier_small: str = "gpt-4o-mini"
    model_tier_medium: str = "gpt-4o"
    model_tier_large: str = "claude-sonnet-4-20250514"
    model_tier_reasoning: str = "o1"
    vision_models: str = "gpt-4o,gemini-1.5-pro,claude-sonnet-4-20250514"
    model_fallback_chain: str = "gpt-4o,claude-sonnet-4-20250514,gemini-1.5-pro"
    tier_small_max_tokens: int = 500
    tier_medium_max_tokens: int = 2000
    agent_recursion_limit: int = 25

    # -------------------------------------------------------------------------
    # Cost Controls
    # -------------------------------------------------------------------------
    session_cost_cap_usd: float = 5.00
    request_cost_cap_usd: float = 1.00
    cost_alert_threshold: float = 0.80

    # -------------------------------------------------------------------------
    # Tools
    # -------------------------------------------------------------------------
    tavily_api_key: str = ""
    tavily_max_results: int = 5
    tavily_search_depth: str = "advanced"

    # Sandbox
    sandbox_image: str = "omniengine/sandbox:latest"
    sandbox_timeout_seconds: int = 30
    sandbox_max_memory: str = "256m"
    sandbox_max_cpu: float = 0.5
    sandbox_network_disabled: bool = True
    sandbox_host: str = "localhost"
    sandbox_port: int = 8001

    # Vision
    vision_default_model: str = "gpt-4o"
    vision_max_image_size_mb: int = 20

    # -------------------------------------------------------------------------
    # Memory & Context
    # -------------------------------------------------------------------------
    context_summarization_threshold: float = 0.70
    memory_rolling_buffer_size: int = 20
    memory_top_k: int = 5
    embedding_model: str = "text-embedding-3-small"

    # -------------------------------------------------------------------------
    # Safety
    # -------------------------------------------------------------------------
    safety_confidence_threshold: float = 0.60
    max_tool_failures: int = 3
    pii_redaction_enabled: bool = True

    # -------------------------------------------------------------------------
    # Telemetry
    # -------------------------------------------------------------------------
    telemetry_enabled: bool = True
    telemetry_batch_size: int = 50

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------
    cleanup_interval_seconds: int = 3600
    cleanup_max_session_age: int = 86400
    cleanup_max_sandbox_age: int = 86400

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------
    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def api_key_list(self) -> list[str]:
        """Parse API keys from comma-separated string."""
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]

    @property
    def vision_model_list(self) -> list[str]:
        """Parse vision-capable model names."""
        return [m.strip() for m in self.vision_models.split(",") if m.strip()]

    @property
    def fallback_chain_list(self) -> list[str]:
        """Parse model fallback chain."""
        return [m.strip() for m in self.model_fallback_chain.split(",") if m.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_testing(self) -> bool:
        return self.environment == "testing"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith(("postgresql+asyncpg://", "sqlite+aiosqlite://")):
            msg = "DATABASE_URL must use an async driver (postgresql+asyncpg:// or sqlite+aiosqlite://)"
            raise ValueError(msg)
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Cached settings factory.

    Returns the same Settings instance for the lifetime of the process.
    Use dependency injection in FastAPI routes via `Depends(get_settings)`.
    """
    return Settings()
