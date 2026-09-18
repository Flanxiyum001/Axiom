"""AXIOM domain model.

Typed domain objects shared by agents, execution, memory and API layers.
Agents must communicate through these objects, never arbitrary dicts.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


def new_id(prefix: str) -> str:
    """Generate a prefixed unique identifier, e.g. ``obj_a1b2c3d4``."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    """Current UTC time (timezone-aware)."""
    return datetime.now(UTC)


class Direction(str, Enum):
    """Whether a metric should be minimized or maximized."""

    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class RunStatus(str, Enum):
    """Lifecycle of an experiment run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class Constraints(BaseModel):
    """Constraints attached to a research objective."""

    max_runtime_seconds: float | None = None
    allowed_dependencies: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ResearchObjective(BaseModel):
    """A measurable research goal, e.g. 'reduce inference latency by 20%'."""

    model_config = ConfigDict(frozen=False)

    id: str = Field(default_factory=lambda: new_id("obj"))
    description: str
    metric: str
    direction: Direction
    target: float
    constraints: Constraints = Field(default_factory=Constraints)
    created_at: datetime = Field(default_factory=utcnow)


class ExpectedEffect(BaseModel):
    """What the hypothesis predicts will happen, quantitatively."""

    metric: str
    direction: Direction
    magnitude_percent: float = Field(description="Expected relative change in percent")
    rationale: str = ""


class Hypothesis(BaseModel):
    """A testable prediction in service of an objective."""

    id: str = Field(default_factory=lambda: new_id("hyp"))
    objective_id: str
    statement: str
    rationale: str
    expected_effect: ExpectedEffect | None = None
    iteration: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class PlanVariable(BaseModel):
    """A single controlled variable in an experiment plan."""

    name: str
    baseline_value: str | None = None
    candidate_value: str | None = None


class ExperimentPlan(BaseModel):
    """How a hypothesis will be tested: baseline vs candidate conditions."""

    id: str = Field(default_factory=lambda: new_id("plan"))
    hypothesis_id: str
    baseline_id: str | None = None
    variables: list[PlanVariable] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    repetitions: int = Field(default=3, ge=1)
    timeout_seconds: float = Field(default=120.0, gt=0)
    created_at: datetime = Field(default_factory=utcnow)


class ExperimentSpec(BaseModel):
    """The exact, executable definition of an experiment.

    ``code`` is executed verbatim by the executor in an isolated sandbox.
    """

    id: str = Field(default_factory=lambda: new_id("exp"))
    plan_id: str
    name: str
    description: str
    code: str
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    environment: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class MetricSample(BaseModel):
    """One measured metric value produced by the experiment runner."""

    name: str
    value: float
    unit: str | None = None
    iteration: int = 0


class Artifact(BaseModel):
    """A file produced by a run, stored by the artifact store."""

    name: str
    path: str
    sha256: str | None = None
    size_bytes: int | None = None


class ExperimentRun(BaseModel):
    """A single execution of an experiment spec, with raw measurements."""

    id: str = Field(default_factory=lambda: new_id("run"))
    experiment_id: str
    status: RunStatus = RunStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    metrics: list[MetricSample] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)


class StatisticalInfo(BaseModel):
    """Aggregated statistics across repetitions of a metric."""

    metric: str
    repetitions: int
    mean: float
    stdev: float = 0.0
    min: float
    max: float
    direction: Direction


class Evaluation(BaseModel):
    """Deterministic comparison of candidate vs baseline metrics.

    Produced exclusively by ExperimentEvaluator code - never by an LLM.
    """

    id: str = Field(default_factory=lambda: new_id("eval"))
    run_id: str
    baseline_run_id: str | None = None
    baseline_metrics: dict[str, float] = Field(default_factory=dict)
    candidate_metrics: dict[str, float] = Field(default_factory=dict)
    deltas: dict[str, float] = Field(default_factory=dict)
    improvement_percent: float | None = None
    target: float | None = None
    target_met: bool = False
    statistics: list[StatisticalInfo] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class Evidence(BaseModel):
    """Analyst interpretation of a deterministic evaluation."""

    id: str = Field(default_factory=lambda: new_id("ev"))
    evaluation_id: str
    hypothesis_id: str
    objective_id: str
    hypothesis_supported: bool
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    observations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    conclusion: str
    created_at: datetime = Field(default_factory=utcnow)


class ResearchHistory(BaseModel):
    """The full provenance chain for one hypothesis, in order."""

    objective: ResearchObjective
    hypothesis: Hypothesis
    plan: ExperimentPlan
    spec: ExperimentSpec
    runs: list[ExperimentRun] = Field(default_factory=list)
    evaluation: Evaluation | None = None
    evidence: Evidence | None = None


class LoopSummary(BaseModel):
    """Result of one full research-loop iteration."""

    iteration: int
    objective: ResearchObjective
    hypothesis: Hypothesis | None = None
    plan: ExperimentPlan | None = None
    spec: ExperimentSpec | None = None
    run_ids: list[str] = Field(default_factory=list)
    evaluation: Evaluation | None = None
    evidence: Evidence | None = None
    target_met: bool = False
    stopped: bool = False
    stop_reason: str | None = None
