from __future__ import annotations

import os

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "AXIOM"
    reasoning_provider: str = Field(default="echo")
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

    def __init__(self, **data: object) -> None:
        env_data: dict[str, object] = {}
        if "reasoning_provider" not in data and os.environ.get("AXIOM_REASONING_PROVIDER"):
            env_data["reasoning_provider"] = os.environ["AXIOM_REASONING_PROVIDER"]
        if "max_iterations" not in data and os.environ.get("AXIOM_MAX_ITERATIONS"):
            env_data["max_iterations"] = int(os.environ["AXIOM_MAX_ITERATIONS"])
        if "run_timeout_seconds" not in data and os.environ.get("AXIOM_RUN_TIMEOUT_SECONDS"):
            env_data["run_timeout_seconds"] = float(os.environ["AXIOM_RUN_TIMEOUT_SECONDS"])
        if "db_path" not in data and os.environ.get("AXIOM_DB_PATH"):
            env_data["db_path"] = os.environ["AXIOM_DB_PATH"]
        if "artifact_root" not in data and os.environ.get("AXIOM_ARTIFACT_ROOT"):
            env_data["artifact_root"] = os.environ["AXIOM_ARTIFACT_ROOT"]
        # Nebius env vars – only read when not explicitly provided in data
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
        super().__init__(**{**env_data, **data})
