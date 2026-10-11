from __future__ import annotations

import os

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "AXIOM"
    reasoning_provider: str = Field(default="echo")
    executor_backend: str = Field(default="local")
    max_iterations: int = Field(default=5, ge=1, le=100)
    run_timeout_seconds: float = Field(default=120.0, gt=0)
    db_path: str = "axiom.db"
    artifact_root: str = "artifacts"

    # Nebius provider configuration (optional)
    nebius_api_key: str | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    nebius_model: str = "nvidia/nemotron-3-super-120b-a12b"
    nebius_request_timeout: float = 60.0
    nebius_max_retries: int = 3

    # Nebius GPU executor configuration (optional)
    nebius_gpu_instance_type: str = "gpu_k8s_a100"
    nebius_gpu_count: int = Field(default=1, ge=1)
    nebius_container_image: str | None = None
    nebius_artifact_store_uri: str | None = None
    nebius_max_wall_time_seconds: float = Field(default=3600.0, gt=0)

    # Nebius S3-compatible object storage configuration (optional)
    nebius_s3_access_key_id: str | None = None
    nebius_s3_secret_access_key: str | None = None
    nebius_s3_region: str = "us-east-1"
    nebius_s3_endpoint_url: str = "https://storage.nebius.com"
    nebius_s3_bucket_name: str | None = None

    def __init__(self, **data: object) -> None:
        env_data: dict[str, object] = {}

        # Canonical API name first; keep the older documented variable as a
        # compatibility alias. The legacy value "mock" maps to the canonical
        # deterministic EchoReasoningProvider.
        if "reasoning_provider" not in data:
            provider = os.environ.get("AXIOM_REASONING_PROVIDER")
            if not provider or not provider.strip():
                provider = os.environ.get("AXIOM_LLM_PROVIDER")
            if provider and provider.strip():
                normalized_provider = provider.strip().lower()
                env_data["reasoning_provider"] = (
                    "echo" if normalized_provider == "mock" else normalized_provider
                )

        if "executor_backend" not in data and os.environ.get("AXIOM_EXECUTOR_BACKEND"):
            env_data["executor_backend"] = os.environ["AXIOM_EXECUTOR_BACKEND"]
        if "max_iterations" not in data and os.environ.get("AXIOM_MAX_ITERATIONS"):
            env_data["max_iterations"] = int(os.environ["AXIOM_MAX_ITERATIONS"])
        if "run_timeout_seconds" not in data and os.environ.get("AXIOM_RUN_TIMEOUT_SECONDS"):
            env_data["run_timeout_seconds"] = float(os.environ["AXIOM_RUN_TIMEOUT_SECONDS"])
        if "db_path" not in data and os.environ.get("AXIOM_DB_PATH"):
            env_data["db_path"] = os.environ["AXIOM_DB_PATH"]
        if "artifact_root" not in data and os.environ.get("AXIOM_ARTIFACT_ROOT"):
            env_data["artifact_root"] = os.environ["AXIOM_ARTIFACT_ROOT"]

        # Nebius env vars – only read when not explicitly provided in data.
        if "nebius_api_key" not in data and os.environ.get("NEBIUS_API_KEY"):
            env_data["nebius_api_key"] = os.environ["NEBIUS_API_KEY"]
        if "nebius_base_url" not in data and os.environ.get("NEBIUS_BASE_URL"):
            env_data["nebius_base_url"] = os.environ["NEBIUS_BASE_URL"]
        if "nebius_model" not in data and os.environ.get("NEBIUS_MODEL"):
            env_data["nebius_model"] = os.environ["NEBIUS_MODEL"]
        if "nebius_request_timeout" not in data and os.environ.get("NEBIUS_REQUEST_TIMEOUT"):
            env_data["nebius_request_timeout"] = float(os.environ["NEBIUS_REQUEST_TIMEOUT"])
        if "nebius_max_retries" not in data and os.environ.get("NEBIUS_MAX_RETRIES"):
            env_data["nebius_max_retries"] = int(os.environ["NEBIUS_MAX_RETRIES"])
        if "nebius_gpu_instance_type" not in data and os.environ.get("NEBIUS_GPU_INSTANCE_TYPE"):
            env_data["nebius_gpu_instance_type"] = os.environ["NEBIUS_GPU_INSTANCE_TYPE"]
        if "nebius_gpu_count" not in data and os.environ.get("NEBIUS_GPU_COUNT"):
            env_data["nebius_gpu_count"] = int(os.environ["NEBIUS_GPU_COUNT"])
        if "nebius_container_image" not in data and os.environ.get("NEBIUS_CONTAINER_IMAGE"):
            env_data["nebius_container_image"] = os.environ["NEBIUS_CONTAINER_IMAGE"]
        if "nebius_artifact_store_uri" not in data and os.environ.get("NEBIUS_ARTIFACT_STORE_URI"):
            env_data["nebius_artifact_store_uri"] = os.environ["NEBIUS_ARTIFACT_STORE_URI"]
        if "nebius_max_wall_time_seconds" not in data and os.environ.get("NEBIUS_MAX_WALL_TIME_SECONDS"):
            env_data["nebius_max_wall_time_seconds"] = float(os.environ["NEBIUS_MAX_WALL_TIME_SECONDS"])
        if "nebius_s3_access_key_id" not in data and os.environ.get("NEBIUS_S3_ACCESS_KEY_ID"):
            env_data["nebius_s3_access_key_id"] = os.environ["NEBIUS_S3_ACCESS_KEY_ID"]
        if "nebius_s3_secret_access_key" not in data and os.environ.get("NEBIUS_S3_SECRET_ACCESS_KEY"):
            env_data["nebius_s3_secret_access_key"] = os.environ["NEBIUS_S3_SECRET_ACCESS_KEY"]
        if "nebius_s3_region" not in data and os.environ.get("NEBIUS_S3_REGION"):
            env_data["nebius_s3_region"] = os.environ["NEBIUS_S3_REGION"]
        if "nebius_s3_endpoint_url" not in data and os.environ.get("NEBIUS_S3_ENDPOINT_URL"):
            env_data["nebius_s3_endpoint_url"] = os.environ["NEBIUS_S3_ENDPOINT_URL"]
        if "nebius_s3_bucket_name" not in data and os.environ.get("NEBIUS_S3_BUCKET_NAME"):
            env_data["nebius_s3_bucket_name"] = os.environ["NEBIUS_S3_BUCKET_NAME"]

        super().__init__(**{**env_data, **data})
