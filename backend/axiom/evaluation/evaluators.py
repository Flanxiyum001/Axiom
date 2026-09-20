"""Built-in evaluators: latency, token usage, and basic response checks."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from axiom.evaluation.base import Evaluator
from axiom.evaluation.models import EvaluatorOutcome
from axiom.experiments.runner import ExperimentResult

_TEXT_FIELDS = ("answer", "text", "content", "output", "response", "conclusion")


def _extract_text(output: BaseModel) -> str:
    """Use the first present text field, falling back to raw JSON."""
    for field in _TEXT_FIELDS:
        value = getattr(output, field, None)
        if isinstance(value, str):
            return value
    return output.model_dump_json()


class LatencyEvaluator(Evaluator):
    """Passes when measured latency stays within budget."""

    name = "latency"

    def __init__(self, threshold_ms: float) -> None:
        """Reject a non-positive latency budget at configuration time."""
        if threshold_ms <= 0:
            raise ValueError(f"threshold_ms must be positive, got {threshold_ms}")
        self.threshold_ms = threshold_ms

    def evaluate(self, result: ExperimentResult) -> EvaluatorOutcome:
        """Compare the measured latency against the configured budget."""
        passed = result.latency_ms <= self.threshold_ms
        return EvaluatorOutcome(
            evaluator=self.name,
            passed=passed,
            score=result.latency_ms,
            details=f"latency {result.latency_ms:.2f}ms vs budget {self.threshold_ms:.2f}ms",
        )


class TokenUsageEvaluator(Evaluator):
    """Reports token usage against an optional budget; inconclusive when absent."""

    name = "token_usage"

    def __init__(self, budget_tokens: int | None = None) -> None:
        """Set an optional total-token budget; without one, only report usage."""
        if budget_tokens is not None and budget_tokens <= 0:
            raise ValueError(f"budget_tokens must be positive, got {budget_tokens}")
        self.budget_tokens = budget_tokens

    def evaluate(self, result: ExperimentResult) -> EvaluatorOutcome:
        """Compare total tokens against the budget, or report when unavailable."""
        total = result.total_tokens
        if total is None:
            return EvaluatorOutcome(
                evaluator=self.name,
                passed=None,
                details="Token usage unavailable",
            )
        if self.budget_tokens is None:
            return EvaluatorOutcome(
                evaluator=self.name,
                passed=None,
                score=float(total),
                details=f"Reported {total} total tokens (no budget configured)",
            )
        passed = total <= self.budget_tokens
        return EvaluatorOutcome(
            evaluator=self.name,
            passed=passed,
            score=float(total),
            details=f"total {total} tokens vs budget {self.budget_tokens}",
        )


class ResponseEvaluator(Evaluator):
    """Checks that the provider returned non-empty content."""

    name = "response"

    def __init__(
        self,
        min_length: int = 1,
        text_extractor: Callable[[BaseModel], str] | None = None,
    ) -> None:
        """Require extracted text of at least min_length via an optional extractor."""
        if min_length < 1:
            raise ValueError(f"min_length must be at least 1, got {min_length}")
        self.min_length = min_length
        self._extractor = text_extractor

    def evaluate(self, result: ExperimentResult) -> EvaluatorOutcome:
        """Fail empty or missing output; otherwise check extracted text length."""
        if result.output is None:
            return EvaluatorOutcome(
                evaluator=self.name,
                passed=False,
                details="No output to evaluate",
            )
        extractor = self._extractor or _extract_text
        text = extractor(result.output)
        passed = len(text.strip()) >= self.min_length
        return EvaluatorOutcome(
            evaluator=self.name,
            passed=passed,
            score=float(len(text)),
            details=f"text length {len(text)} vs minimum {self.min_length}",
        )
