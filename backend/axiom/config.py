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
        super().__init__(**{**env_data, **data})
