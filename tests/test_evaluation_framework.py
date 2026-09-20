"""Framework behavior: aggregation, isolation, failure handling, input safety."""

from pydantic import BaseModel

from axiom.evaluation.base import Evaluator
from axiom.evaluation.evaluators import (
    LatencyEvaluator,
    ResponseEvaluator,
    TokenUsageEvaluator,
)
from axiom.evaluation.framework import EvaluationFramework
from axiom.evaluation.models import EvaluatorOutcome
from axiom.experiments.runner import ExperimentResult


class TextOutput(BaseModel):
    """Simple text output for response evaluation."""

    answer: str


def _result(**overrides):
    """Build an experiment result with sane defaults for evaluation tests."""
    fields = {"status": "completed", "latency_ms": 10.0, "provider": "stub"}
    fields.update(overrides)
    return ExperimentResult(**fields)


def test_latency_passes_within_budget():
    """Latency at or under budget passes and reports the measurement."""
    outcome = LatencyEvaluator(threshold_ms=10.0).evaluate(_result(latency_ms=10.0))
    assert outcome.passed is True
    assert outcome.score == 10.0


def test_latency_fails_over_budget():
    """Latency above budget fails with both values in details."""
    outcome = LatencyEvaluator(threshold_ms=10.0).evaluate(_result(latency_ms=25.5))
    assert outcome.passed is False
    assert outcome.score == 25.5
    assert "25.50" in outcome.details


def test_latency_rejects_non_positive_budget():
    """Budget configuration fails fast instead of mis-evaluating later."""
    try:
        LatencyEvaluator(threshold_ms=0)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_tokens_inconclusive_when_unavailable():
    """Missing usage reports inconclusive rather than failing the run."""
    outcome = TokenUsageEvaluator(budget_tokens=100).evaluate(_result(total_tokens=None))
    assert outcome.passed is None
    assert outcome.score is None


def test_tokens_pass_and_fail_against_budget():
    """Usage under budget passes; usage over budget fails."""
    evaluator = TokenUsageEvaluator(budget_tokens=100)
    assert evaluator.evaluate(_result(total_tokens=100)).passed is True
    assert evaluator.evaluate(_result(total_tokens=101)).passed is False


def test_tokens_report_without_budget():
    """Without a budget the evaluator only reports the observed total."""
    outcome = TokenUsageEvaluator().evaluate(_result(total_tokens=50))
    assert outcome.passed is None
    assert outcome.score == 50.0


def test_response_passes_on_text():
    """Non-empty extracted text passes the basic content check."""
    outcome = ResponseEvaluator().evaluate(_result(output=TextOutput(answer="hello")))
    assert outcome.passed is True


def test_response_fails_on_missing_or_blank_output():
    """Missing output fails; blank text fails the minimum length."""
    assert ResponseEvaluator().evaluate(_result(output=None)).passed is False
    assert ResponseEvaluator().evaluate(_result(output=TextOutput(answer="  "))).passed is False


def test_response_supports_custom_extractor():
    """Callers can override text extraction for schemas without text fields."""
    evaluator = ResponseEvaluator(text_extractor=lambda output: "custom!")
    assert evaluator.evaluate(_result(output=TextOutput(answer=""))).passed is True


def test_framework_aggregates_all_pass():
    """Every evaluator passing yields an overall pass."""
    framework = EvaluationFramework([LatencyEvaluator(100.0), ResponseEvaluator()])
    evaluation = framework.evaluate(_result(output=TextOutput(answer="ok")))
    assert evaluation.passed is True
    assert len(evaluation.outcomes) == 2
    assert evaluation.evaluated_at is not None


def test_framework_one_failure_fails_overall():
    """A single failed evaluator fails the overall verdict."""
    framework = EvaluationFramework([LatencyEvaluator(100.0), LatencyEvaluator(1.0)])
    assert framework.evaluate(_result()).passed is False


def test_framework_all_inconclusive_stays_inconclusive():
    """No decisive verdict keeps the overall result inconclusive."""
    framework = EvaluationFramework([TokenUsageEvaluator()])
    assert framework.evaluate(_result(total_tokens=None)).passed is None


def test_register_adds_evaluator_without_core_changes():
    """New evaluators plug in via register; frameworks stay independent."""
    first = EvaluationFramework()
    second = EvaluationFramework()
    second.register(LatencyEvaluator(100.0))
    assert first.evaluators == ()
    assert len(second.evaluators) == 1
    assert second.evaluate(_result()).passed is True


def test_custom_evaluator_plugs_in():
    """Any Evaluator implementation participates in aggregation."""
    from axiom.evaluation.models import EvaluatorOutcome as Outcome

    class AlwaysPass(Evaluator):
        name = "custom"

        def evaluate(self, result):
            return Outcome(evaluator=self.name, passed=True, details="ok")

    evaluation = EvaluationFramework([AlwaysPass()]).evaluate(_result())
    assert evaluation.passed is True
    assert evaluation.outcomes[0].evaluator == "custom"


def test_exploding_evaluator_becomes_failed_outcome():
    """A crashing evaluator fails its own outcome without killing the run."""
    class Exploding(Evaluator):
        name = "boom"

        def evaluate(self, result):
            raise RuntimeError("kaput")

    evaluation = EvaluationFramework([Exploding(), LatencyEvaluator(100.0)]).evaluate(_result())
    assert evaluation.passed is False
    failed = [o for o in evaluation.outcomes if o.evaluator == "boom"][0]
    assert failed.error is not None
    assert "kaput" in failed.error


def test_bad_return_type_becomes_failed_outcome():
    """An evaluator returning the wrong type fails instead of corrupting results."""
    class Sloppy(Evaluator):
        name = "sloppy"

        def evaluate(self, result):
            return {"passed": True}

    evaluation = EvaluationFramework([Sloppy()]).evaluate(_result())
    assert evaluation.passed is False
    assert "EvaluatorOutcome" in (evaluation.outcomes[0].error or "")


def test_invalid_input_raises_type_error():
    """Non-result input is programmer error and raises instead of evaluating."""
    framework = EvaluationFramework([LatencyEvaluator(100.0)])
    for bad in (None, {}, "result"):
        try:
            framework.evaluate(bad)
        except TypeError:
            continue
        raise AssertionError(f"expected TypeError for {bad!r}")


def test_input_result_never_modified():
    """Evaluation snapshots the input; the original object is byte-identical after."""
    result = _result(output=TextOutput(answer="hello"), total_tokens=42)
    before = result.model_dump_json()
    EvaluationFramework(
        [LatencyEvaluator(100.0), TokenUsageEvaluator(100), ResponseEvaluator()]
    ).evaluate(result)
    assert result.model_dump_json() == before


def test_evaluation_links_experiment_reference():
    """The framework result carries the evaluated experiment for traceability."""
    result = _result()
    evaluation = EvaluationFramework([LatencyEvaluator(100.0)]).evaluate(result)
    assert evaluation.experiment.provider == "stub"
    assert evaluation.experiment.latency_ms == 10.0


def test_mutating_evaluator_cannot_corrupt_input_or_peers():
    """Each evaluator gets an isolated copy; mutations never leak outward."""
    from axiom.evaluation.models import EvaluatorOutcome as Outcome

    seen = {}

    class Mutator(Evaluator):
        name = "mutator"

        def evaluate(self, result):
            result.latency_ms = 0.0
            result.output.answer = "MUTATED"
            return Outcome(evaluator=self.name, passed=True)

    class Witness(Evaluator):
        name = "witness"

        def evaluate(self, result):
            seen["latency_ms"] = result.latency_ms
            seen["answer"] = result.output.answer
            return Outcome(evaluator=self.name, passed=True)

    result = _result(output=TextOutput(answer="original"))
    evaluation = EvaluationFramework([Mutator(), Witness()]).evaluate(result)
    assert evaluation.passed is True
    assert result.latency_ms == 10.0
    assert result.output.answer == "original"
    assert seen == {"latency_ms": 10.0, "answer": "original"}


def test_nameless_evaluator_never_raises_attribute_error():
    """Evaluators without a usable name still produce labeled failed outcomes."""
    class Nameless:
        @property
        def name(self):
            raise RuntimeError("no name")

        def evaluate(self, result):
            raise RuntimeError("kaput")

    evaluation = EvaluationFramework([Nameless()]).evaluate(_result())
    assert evaluation.passed is False
    assert evaluation.outcomes[0].evaluator == "Nameless"
    assert "kaput" in (evaluation.outcomes[0].error or "")
