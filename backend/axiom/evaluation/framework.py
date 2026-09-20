"""Evaluation framework: runs registered evaluators without touching input."""

from __future__ import annotations

import copy

from axiom.domain.models import utcnow
from axiom.evaluation.base import Evaluator
from axiom.evaluation.models import EvaluationResult, EvaluatorOutcome
from axiom.experiments.runner import ExperimentResult


def _evaluator_name(evaluator: Evaluator) -> str:
    """Resolve a display name that never raises, even for malformed evaluators."""
    try:
        name = evaluator.name
    except Exception:
        return type(evaluator).__name__
    return name if isinstance(name, str) and name else type(evaluator).__name__


class EvaluationFramework:
    """Owns an evaluator set and aggregates their verdicts per result."""

    def __init__(self, evaluators: list[Evaluator] | None = None) -> None:
        """Start with the given evaluators; more can register later."""
        self._evaluators = list(evaluators or [])

    @property
    def evaluators(self) -> tuple[Evaluator, ...]:
        """Snapshot of the registered evaluators in registration order."""
        return tuple(self._evaluators)

    def register(self, evaluator: Evaluator) -> None:
        """Add an evaluator without modifying the framework or the others."""
        self._evaluators.append(evaluator)

    def evaluate(self, result: ExperimentResult) -> EvaluationResult:
        """Run every evaluator; crashes become failed outcomes, input untouched."""
        if not isinstance(result, ExperimentResult):
            raise TypeError(f"Expected ExperimentResult, got {type(result).__name__}")
        outcomes = [self._guarded(evaluator, result) for evaluator in self._evaluators]
        flags = [outcome.passed for outcome in outcomes]
        if any(flag is False for flag in flags):
            passed: bool | None = False
        elif any(flag is True for flag in flags):
            passed = True
        else:
            passed = None
        return EvaluationResult(
            experiment=result,
            outcomes=outcomes,
            passed=passed,
            evaluated_at=utcnow(),
        )

    def _guarded(self, evaluator: Evaluator, result: ExperimentResult) -> EvaluatorOutcome:
        """Run one evaluator on an isolated copy, converting failures into outcomes."""
        name = _evaluator_name(evaluator)
        try:
            isolated = copy.deepcopy(result)
        except Exception as exc:
            return EvaluatorOutcome(
                evaluator=name,
                passed=False,
                error=f"Could not isolate input: {type(exc).__name__}: {exc}",
            )
        try:
            outcome = evaluator.evaluate(isolated)
        except Exception as exc:
            return EvaluatorOutcome(
                evaluator=name,
                passed=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        if not isinstance(outcome, EvaluatorOutcome):
            return EvaluatorOutcome(
                evaluator=name,
                passed=False,
                error=f"Evaluator returned {type(outcome).__name__}, expected EvaluatorOutcome",
            )
        if not outcome.evaluator:
            outcome.evaluator = name
        return outcome
