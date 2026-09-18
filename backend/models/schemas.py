from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

class MetricDirection(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"

class ExperimentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class MetricDefinition(BaseModel):
    name: str
    unit: str
    direction: MetricDirection

class ResearchObjective(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    metrics: List[MetricDefinition]
    constraints: Dict[str, Any]
    target: Dict[str, Any]
    max_experiments: int = 10

class Hypothesis(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    objective_id: UUID
    title: str
    description: str
    rationale: str
    expected_outcome: str
    status: ExperimentStatus = ExperimentStatus.PENDING

class ExperimentPlan(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    hypothesis_id: UUID
    title: str
    description: str
    parameters: Dict[str, Any]
    metrics: List[str]
    success_criteria: str

class Metric(BaseModel):
    name: str
    value: float
    unit: str
    direction: MetricDirection

class ExperimentResult(BaseModel):
    experiment_id: UUID
    status: ExperimentStatus
    metrics: List[Metric]
    duration: float  # seconds
    logs: str
    error: Optional[str] = None
    conclusion: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class ResearchMemoryEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    experiment_id: UUID
    objective_id: UUID
    hypothesis: Optional[str] = None
    observation: str
    conclusion: str
    suggested_next_steps: str
    timestamp: datetime = Field(default_factory=datetime.now)


class Analysis(BaseModel):
    """Structured Analyst output: interpretation of experiment results.

    The Analyst does NOT override evaluator results. It interprets the
    deterministic evaluation evidence and produces a structured analysis
    with observations, interpretation, limitations, and recommended next
    direction.
    """
    id: UUID = Field(default_factory=uuid4)
    experiment_id: UUID
    objective_id: UUID
    hypothesis_id: Optional[UUID] = None
    hypothesis_title: Optional[str] = None
    summary: str
    observations: List[str]
    interpretation: str
    limitations: List[str]
    recommended_next_direction: str
    timestamp: datetime = Field(default_factory=datetime.now)

