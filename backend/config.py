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

    # Nebius S3 configuration (optional)
    nebius_s3_access_key_id: Optional[str] = Field(
        default=None,
        alias="NEBIUS_S3_ACCESS_KEY_ID",
        description="Nebius S3 access key ID",
    )
    nebius_s3_secret_access_key: Optional[str] = Field(
        default=None,
        alias="NEBIUS_S3_SECRET_ACCESS_KEY",
        description="Nebius S3 secret access key",
    )
    nebius_s3_region: str = Field(
        default="us-east-1",
        alias="NEBIUS_S3_REGION",
        description="Nebius S3 region",
    )
    nebius_s3_endpoint_url: str = Field(
        default="https://storage.nebius.com",
        alias="NEBIUS_S3_ENDPOINT_URL",
        description="Nebius S3 endpoint URL",
    )
    nebius_s3_bucket_name: str | None = Field(
        default=None,
        alias="NEBIUS_S3_BUCKET_NAME",
        description="Nebius S3 bucket name for artifact storage",
    )

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


settings = Settings()
