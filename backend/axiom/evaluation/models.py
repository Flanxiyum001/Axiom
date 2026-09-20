"""Evaluation schemas: per-evaluator outcomes and the aggregated result."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from axiom.domain.models import utcnow
from axiom.experiments.runner import ExperimentResult


class EvaluatorOutcome(BaseModel):
    """Verdict of one evaluator: pass, fail, or inconclusive, with details."""

    evaluator: str
    passed: bool | None = None
    score: float | None = None
    details: str = ""
    error: str | None = None


class EvaluationResult(BaseModel):
    """Aggregated verdicts for one experiment result, which is never modified."""

    experiment: ExperimentResult
    outcomes: list[EvaluatorOutcome] = Field(default_factory=list)
    passed: bool | None = None
    evaluated_at: datetime = Field(default_factory=utcnow)
