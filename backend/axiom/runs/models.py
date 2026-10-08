"""Run schemas: status, execution config, and the benchmark run record."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from axiom.domain.models import new_id, utcnow
from axiom.pipeline.models import CaseFailure
from axiom.reporting.models import BenchmarkReport, CaseRecord


class BenchmarkRunStatus(str, Enum):
    """Lifecycle of a benchmark run, following RunStatus conventions."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ExecutionConfig(BaseModel):
    """Reproducibility metadata: everything known about how a run executed."""

    dataset: str
    dataset_description: str = ""
    dataset_version: str = ""
    case_ids: list[str] = Field(default_factory=list)
    label: str = ""
    system: str = ""
    output_schema: str = ""
    providers: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    evaluator_names: list[str] = Field(default_factory=list)
    max_concurrency: int = 1
    fail_fast: bool = False
    seed: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    extra: dict[str, str] = Field(default_factory=dict)


class BenchmarkRun(BaseModel):
    """Complete trace of one benchmark execution, loadable for analysis."""

    id: str = Field(default_factory=lambda: new_id("brun"))
    status: BenchmarkRunStatus = BenchmarkRunStatus.COMPLETED
    config: ExecutionConfig
    records: list[CaseRecord] = Field(default_factory=list)
    failures: list[CaseFailure] = Field(default_factory=list)
    report: BenchmarkReport | None = None
    started_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime = Field(default_factory=utcnow)
