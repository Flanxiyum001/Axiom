"""Pipeline schemas: per-case failures and the aggregated pipeline result."""

from __future__ import annotations

from pydantic import BaseModel, Field

from axiom.reporting.models import BenchmarkReport, CaseRecord


class CaseFailure(BaseModel):
    """A case that never became a record, with its stage and error."""

    case_id: str
    stage: str
    error: str


class PipelineResult(BaseModel):
    """Full pipeline outcome: report over successes plus every failure."""

    benchmark: str
    label: str = ""
    report: BenchmarkReport | None = None
    records: list[CaseRecord] = Field(default_factory=list)
    failures: list[CaseFailure] = Field(default_factory=list)
