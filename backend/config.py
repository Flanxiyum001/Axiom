"""Configuration for AXIOM.

Supports:
- AXIOM_LLM_PROVIDER: "mock" (default) or "nebius"
- NEBIUS_API_KEY, NEBIUS_BASE_URL, NEBIUS_MODEL for Nebius Token Factory
- General app settings
"""

from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    app_name: str = "AXIOM"
    environment: str = "development"
    log_level: str = "INFO"

    # LLM Provider Selection
    # Default is "mock" so tests remain offline and deterministic.
    # Set to "nebius" to use the Nebius Token Factory API.
    axiom_llm_provider: str = Field(
        default="mock",
        alias="AXIOM_LLM_PROVIDER",
        description="LLM provider: mock or nebius",
    )

    # Nebius Token Factory configuration
    nebius_api_key: Optional[str] = Field(
        default=None,
        alias="NEBIUS_API_KEY",
        description="Nebius Token Factory API key",
    )
    nebius_base_url: str = Field(
        default="https://api.tokenfactory.nebius.com/v1/",
        alias="NEBIUS_BASE_URL",
        description="Nebius Token Factory base URL",
    )
    nebius_model: str = Field(
        default="meta-llama/Meta-Llama-3.1-70B-Instruct",
        alias="NEBIUS_MODEL",
        description="Nebius model identifier (OpenAI-compatible)",
    )
    nebius_request_timeout: float = Field(
        default=60.0,
        alias="NEBIUS_REQUEST_TIMEOUT",
        description="Request timeout in seconds",
    )
    nebius_max_retries: int = Field(
        default=3,
        alias="NEBIUS_MAX_RETRIES",
        description="Maximum retries on transient failures",
    )

    # Mock provider seed for deterministic behavior
    mock_seed: int = Field(
        default=42,
        alias="MOCK_SEED",
        description="Seed for mock LLM provider determinism",
    )

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


settings = Settings()
