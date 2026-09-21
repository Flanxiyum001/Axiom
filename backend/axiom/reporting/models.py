"""Reporting schemas: records, per-evaluator summaries, reports, comparisons."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from axiom.domain.models import utcnow
from axiom.evaluation.models import EvaluationResult
from axiom.experiments.runner import ExperimentResult


class CaseRecord(BaseModel):
    """One benchmark case with its paired experiment and evaluation results."""

    case_id: str
    experiment: ExperimentResult
    evaluation: EvaluationResult

    @model_validator(mode="after")
    def _experiments_match(self) -> CaseRecord:
        """Reject records attributing outcomes to the wrong experiment."""
        if self.experiment != self.evaluation.experiment:
            raise ValueError(f"Case {self.case_id!r} pairs mismatched experiments")
        return self


class EvaluatorSummary(BaseModel):
    """Score statistics and verdict counts for one evaluator across cases."""

    evaluator: str
    scored: int = 0
    mean: float | None = None
    min: float | None = None
    max: float | None = None
    passed: int = 0
    failed: int = 0
    inconclusive: int = 0


class BenchmarkReport(BaseModel):
    """Aggregated report for one benchmark run, preserving every record."""

    benchmark: str
    label: str = ""
    cases: int = 0
    summaries: list[EvaluatorSummary] = Field(default_factory=list)
    records: list[CaseRecord] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utcnow)

    def summary_for(self, evaluator: str) -> EvaluatorSummary | None:
        """Fetch the summary for one evaluator, or None when absent."""
        for summary in self.summaries:
            if summary.evaluator == evaluator:
                return summary
        return None


class MetricComparison(BaseModel):
    """Mean shift for one evaluator shared by two compared reports."""

    evaluator: str
    baseline_mean: float | None = None
    candidate_mean: float | None = None
    delta: float | None = None


class ComparisonReport(BaseModel):
    """Side-by-side verdict for two reports of (usually) one benchmark."""

    baseline_label: str = ""
    candidate_label: str = ""
    comparisons: list[MetricComparison] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utcnow)
