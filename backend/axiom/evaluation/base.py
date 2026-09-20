"""Evaluator interface: the contract every metric evaluator implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from axiom.evaluation.models import EvaluatorOutcome
from axiom.experiments.runner import ExperimentResult


class Evaluator(ABC):
    """Pluggable metric check turning an experiment result into an outcome."""

    name: str

    @abstractmethod
    def evaluate(self, result: ExperimentResult) -> EvaluatorOutcome:
        """Assess the result; raise only for unrecoverable evaluator bugs."""
        raise NotImplementedError
