from __future__ import annotations

from pydantic import BaseModel, Field

from axiom.domain.models import PlanVariable


class PlanOutput(BaseModel):
    variables: list[PlanVariable] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    repetitions: int = Field(default=3, ge=1)
    timeout_seconds: float = Field(default=60.0, gt=0)


class CodeOutput(BaseModel):
    code: str
    environment: dict[str, str] = Field(default_factory=dict)
    description: str = ""
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)


class AnalysisOutput(BaseModel):
    hypothesis_supported: bool
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    observations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    conclusion: str = ""
