"""Architectural boundaries for AXIOM.

Every major component implements one of these interfaces. Agents propose and
analyze; deterministic infrastructure validates, executes, measures and
evaluates. An LLM must never decide whether an experiment succeeded.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from axiom.domain.models import (
    Evidence,
    Evaluation,
    ExperimentPlan,
    ExperimentRun,
    ExperimentSpec,
    Hypothesis,
    ResearchObjective,
)

T = TypeVar("T", bound=BaseModel)


class ReasoningProvider(ABC):
    """Abstraction over an LLM that produces *validated structured output*.

    Implementations (echo stub, OpenAI-compatible providers such as Nebius
    Token Factory / Nemotron, etc.) must accept context, call the model, parse
    the reply, validate it against the requested Pydantic type and retry with
    error feedback on validation failures.
    """

    name: str

    @abstractmethod
    def generate(
        self,
        *,
        system: str,
        prompt: str,
        context: dict[str, str],
        output_type: type[T],
    ) -> T:
        """Produce a validated instance of ``output_type`` from the prompt.

        ``context`` carries the current research state as simple key/value
        strings (serialized domain objects). Raise ``ProviderError`` when no
        valid output can be produced.
        """
        raise NotImplementedError


class ProviderError(RuntimeError):
    """Raised when a reasoning provider cannot produce valid output."""


class ExperimentExecutor(ABC):
    """Executes an ExperimentSpec and returns raw, objective measurements."""

    @abstractmethod
    def execute(self, spec: ExperimentSpec, timeout_seconds: float) -> ExperimentRun:
        """Run ``spec`` in an isolated environment; never raises for code errors.

        Failures are captured in the returned run (status, exit_code, stderr).
        """
        raise NotImplementedError


class ExperimentEvaluator(ABC):
    """Deterministic metric comparison. Never implemented by an LLM."""

    @abstractmethod
    def evaluate(
        self,
        *,
        baseline: ExperimentRun,
        candidate: ExperimentRun,
        plan: ExperimentPlan,
        objective: ResearchObjective,
    ) -> Evaluation:
        """Compare runs and compute deltas, improvement and target status."""
        raise NotImplementedError


class MemoryRepository(ABC):
    """Persistence boundary for the complete research history."""

    @abstractmethod
    def save_objective(self, objective: ResearchObjective) -> None: ...
    @abstractmethod
    def get_objective(self, objective_id: str) -> ResearchObjective | None: ...
    @abstractmethod
    def list_objectives(self) -> list[ResearchObjective]: ...

    @abstractmethod
    def save_hypothesis(self, hypothesis: Hypothesis) -> None: ...
    @abstractmethod
    def get_hypothesis(self, hypothesis_id: str) -> Hypothesis | None: ...
    @abstractmethod
    def list_hypotheses(self, objective_id: str) -> list[Hypothesis]: ...

    @abstractmethod
    def save_plan(self, plan: ExperimentPlan) -> None: ...
    @abstractmethod
    def get_plan(self, plan_id: str) -> ExperimentPlan | None: ...

    @abstractmethod
    def save_spec(self, spec: ExperimentSpec) -> None: ...
    @abstractmethod
    def get_spec(self, spec_id: str) -> ExperimentSpec | None: ...

    @abstractmethod
    def save_run(self, run: ExperimentRun) -> None: ...
    @abstractmethod
    def get_run(self, run_id: str) -> ExperimentRun | None: ...
    @abstractmethod
    def list_runs(self, experiment_id: str) -> list[ExperimentRun]: ...

    @abstractmethod
    def save_evaluation(self, evaluation: Evaluation) -> None: ...
    @abstractmethod
    def get_evaluation(self, evaluation_id: str) -> Evaluation | None: ...
    @abstractmethod
    def list_evaluations(self, hypothesis_id: str) -> list[Evaluation]: ...

    @abstractmethod
    def save_evidence(self, evidence: Evidence) -> None: ...
    @abstractmethod
    def get_evidence(self, evidence_id: str) -> Evidence | None: ...

    @abstractmethod
    def next_hypothesis_number(self, objective_id: str) -> int: ...
    @abstractmethod
    def history_for_objective(self, objective_id: str) -> list[ResearchHistory]: ...
