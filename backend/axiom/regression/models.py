"""Regression schemas: status, thresholds, and the regression report."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from axiom.domain.models import Direction, utcnow


class RegressionStatus(str, Enum):
    """Overall or per-metric regression outcome."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class MetricThresholds(BaseModel):
    """Warning/failure limits for one metric, absolute and percentage points."""

    warn_abs: float | None = None
    fail_abs: float | None = None
    warn_pct: float | None = None
    fail_pct: float | None = None

    @field_validator("warn_abs", "fail_abs", "warn_pct", "fail_pct")
    @classmethod
    def _non_negative(cls, value: float | None) -> float | None:
        """Reject negative thresholds; they would trigger on every regression."""
        if value is not None and value < 0:
            raise ValueError("Regression thresholds must be non-negative")
        return value


class RegressionConfig(BaseModel):
    """Threshold configuration with defaults plus per-metric overrides."""

    default_warn_abs: float | None = None
    default_fail_abs: float | None = None
    default_warn_pct: float | None = None
    default_fail_pct: float | None = None
    per_metric: dict[str, MetricThresholds] = Field(default_factory=dict)

    @field_validator(
        "default_warn_abs", "default_fail_abs", "default_warn_pct", "default_fail_pct"
    )
    @classmethod
    def _non_negative(cls, value: float | None) -> float | None:
        """Reject negative default thresholds before they reach evaluation."""
        if value is not None and value < 0:
            raise ValueError("Regression thresholds must be non-negative")
        return value

    def thresholds_for(self, metric: str) -> MetricThresholds:
        """Merge defaults with any per-metric override for one metric."""
        override = self.per_metric.get(metric, MetricThresholds())
        return MetricThresholds(
            warn_abs=override.warn_abs if override.warn_abs is not None else self.default_warn_abs,
            fail_abs=override.fail_abs if override.fail_abs is not None else self.default_fail_abs,
            warn_pct=override.warn_pct if override.warn_pct is not None else self.default_warn_pct,
            fail_pct=override.fail_pct if override.fail_pct is not None else self.default_fail_pct,
        )


class MetricRegression(BaseModel):
    """Regression verdict for one aggregate metric."""

    metric: str
    baseline: float | None = None
    candidate: float | None = None
    delta: float | None = None
    percent: float | None = None
    direction: Direction | None = None
    status: RegressionStatus = RegressionStatus.PASS
    reason: str = ""


class CaseRegression(BaseModel):
    """Regression verdict for one benchmark case."""

    case_id: str
    present_baseline: bool = True
    present_candidate: bool = True
    status: RegressionStatus = RegressionStatus.PASS
    metrics: list[MetricRegression] = Field(default_factory=list)
    reason: str = ""


class RegressionReport(BaseModel):
    """Structured regression outcome derived read-only from a comparison."""

    baseline_run_id: str
    candidate_run_id: str
    benchmark: str = ""
    status: RegressionStatus = RegressionStatus.PASS
    metrics: list[MetricRegression] = Field(default_factory=list)
    cases: list[CaseRegression] = Field(default_factory=list)
    missing_in_candidate: list[str] = Field(default_factory=list)
    missing_in_baseline: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    detected_at: datetime = Field(default_factory=utcnow)
