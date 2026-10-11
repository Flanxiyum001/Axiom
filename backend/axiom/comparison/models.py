"""Comparison schemas: verdicts, deltas, and the run comparison result."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from axiom.domain.models import Direction, utcnow


class MetricVerdict(str, Enum):
    """Outcome of one metric comparison."""

    IMPROVED = "improved"
    REGRESSED = "regressed"
    UNCHANGED = "unchanged"
    UNKNOWN = "unknown"


class MetricDelta(BaseModel):
    """Absolute and percentage change for one metric with its verdict."""

    metric: str
    value_a: float | None = None
    value_b: float | None = None
    delta: float | None = None
    percent: float | None = None
    direction: Direction | None = None
    verdict: MetricVerdict = MetricVerdict.UNKNOWN


class CaseComparison(BaseModel):
    """Per-case metric deltas plus presence on each side."""

    case_id: str
    present_a: bool = True
    present_b: bool = True
    metrics: list[MetricDelta] = Field(default_factory=list)


class MetadataDifference(BaseModel):
    """One configuration field whose values differ between runs."""

    field: str
    value_a: Any = None
    value_b: Any = None


class RunComparison(BaseModel):
    """Structured comparison of two benchmark runs, derived read-only."""

    run_a_id: str
    run_b_id: str
    benchmark: str
    dataset_version: str = ""
    label_a: str = ""
    label_b: str = ""
    providers_a: list[str] = Field(default_factory=list)
    providers_b: list[str] = Field(default_factory=list)
    models_a: list[str] = Field(default_factory=list)
    models_b: list[str] = Field(default_factory=list)
    metadata_differences: list[MetadataDifference] = Field(default_factory=list)
    metrics: list[MetricDelta] = Field(default_factory=list)
    cases: list[CaseComparison] = Field(default_factory=list)
    missing_in_b: list[str] = Field(default_factory=list)
    missing_in_a: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    compared_at: datetime = Field(default_factory=utcnow)
