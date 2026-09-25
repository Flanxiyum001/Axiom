"""Pipeline behavior: full flow, failure isolation, and input validation."""

from pydantic import BaseModel

from axiom.benchmarks.loader import load_dict
from axiom.domain.interfaces import ProviderError, ReasoningProvider
from axiom.evaluation.evaluators import LatencyEvaluator, ResponseEvaluator
from axiom.evaluation.framework import EvaluationFramework
from axiom.pipeline.pipeline import ExperimentPipeline
from axiom.experiments.runner import ExperimentRunner


class TextOutput(BaseModel):
    """Deterministic stub output for pipeline tests."""

    answer: str


class StubProvider(ReasoningProvider):
    """Test double returning canned text or raising on demand."""

    name = "stub"

    def __init__(self, error=None):
        """Optionally fail every provider call with the given error."""
        self.error = error

    def generate(self, *, system, prompt, context, output_type):
        """Return canned text or raise the configured error."""
        if self.error is not None:
            raise self.error
        return TextOutput(answer=f"Answer to {prompt}")


def _dataset():
    """Small two-case dataset exercising the complete pipeline."""
    return load_dict(
        {
            "name": "pipe_benchmark",
            "description": "pipeline test",
            "cases": [
                {"id": "case-001", "input": "First question?"},
                {"id": "case-002", "input": "Second question?"},
            ],
        }
    )


def _pipeline(provider=None, evaluators=None, **kwargs):
    """Build a pipeline with stub defaults overridable per test."""
    runner = ExperimentRunner(provider or StubProvider())
    framework = EvaluationFramework(
        evaluators if evaluators is not None else [LatencyEvaluator(60000.0), ResponseEvaluator()]
    )
    return ExperimentPipeline(runner, framework, **kwargs)


def test_end_to_end_produces_report():
    """Dataset cases flow through run, evaluate, and aggregate to a report."""
    result = _pipeline().run(_dataset(), output_type=TextOutput, label="e2e")
    assert result.benchmark == "pipe_benchmark"
    assert result.label == "e2e"
    assert result.failures == []
    assert len(result.records) == 2
    assert [record.case_id for record in result.records] == ["case-001", "case-002"]
    assert result.report is not None
    assert result.report.cases == 2
    assert result.report.label == "e2e"
    assert result.report.summary_for("response") is not None
    assert result.report.summary_for("response").passed == 2


def test_failed_experiments_stay_visible():
    """Provider failures become failed records, not silent gaps."""
    pipeline = _pipeline(provider=StubProvider(error=ProviderError("down")))
    result = pipeline.run(_dataset(), output_type=TextOutput)
    assert result.failures == []
    assert len(result.records) == 2
    assert result.report is not None
    response = result.report.summary_for("response")
    assert response is not None
    assert response.failed == 2
    assert all(record.experiment.status.value == "failed" for record in result.records)


def test_unexpected_case_error_recorded_not_raised():
    """Broken stages record stage and error while siblings continue."""
    runner = ExperimentRunner(StubProvider())
    original = runner.run

    def broken(request, *, output_type):
        if "Second" in request.prompt:
            raise RuntimeError("kaput")
        return original(request, output_type=output_type)

    runner.run = broken
    pipeline = ExperimentPipeline(runner, EvaluationFramework([ResponseEvaluator()]))
    result = pipeline.run(_dataset(), output_type=TextOutput)
    assert len(result.records) == 1
    assert result.records[0].case_id == "case-001"
    assert len(result.failures) == 1
    assert result.failures[0].case_id == "case-002"
    assert result.failures[0].stage == "run"
    assert "kaput" in result.failures[0].error
    assert result.report is not None
    assert result.report.cases == 1


def test_fail_fast_reraises():
    """Configured fail-fast stops the pipeline on the first broken case."""
    runner = ExperimentRunner(StubProvider())
    original = runner.run

    def broken(request, *, output_type):
        raise RuntimeError("kaput")

    runner.run = broken
    pipeline = ExperimentPipeline(runner, EvaluationFramework(), fail_fast=True)
    try:
        pipeline.run(_dataset(), output_type=TextOutput)
    except RuntimeError as exc:
        assert "kaput" in str(exc)
        return
    raise AssertionError("expected RuntimeError")


def test_evaluate_stage_failures_recorded():
    """Evaluation crashes record the evaluate stage without killing siblings."""
    runner = ExperimentRunner(StubProvider())
    framework = EvaluationFramework()
    original = framework.evaluate

    def broken(result):
        if result.status.value == "completed":
            raise RuntimeError("eval kaput")
        return original(result)

    framework.evaluate = broken
    pipeline = ExperimentPipeline(runner, framework)
    result = pipeline.run(_dataset(), output_type=TextOutput)
    assert result.records == []
    assert len(result.failures) == 2
    assert all(failure.stage == "evaluate" for failure in result.failures)
    assert result.report is None


def test_evaluate_stage_preserves_experiment():
    """Experiments surviving a failed evaluation stay attached to the failure."""
    runner = ExperimentRunner(StubProvider())
    framework = EvaluationFramework()

    def broken(result):
        raise RuntimeError("eval kaput")

    framework.evaluate = broken
    pipeline = ExperimentPipeline(runner, framework)
    result = pipeline.run(_dataset(), output_type=TextOutput)
    assert len(result.failures) == 2
    for failure in result.failures:
        assert failure.experiment is not None
        assert failure.experiment.provider == "stub"


def test_invalid_dataset_raises_type_error():
    """Non-dataset input is programmer error and raises instead of running."""
    pipeline = _pipeline()
    for bad in (None, {}, "dataset"):
        try:
            pipeline.run(bad, output_type=TextOutput)
        except TypeError:
            continue
        raise AssertionError(f"expected TypeError for {bad!r}")


def test_system_prompt_reaches_provider():
    """The pipeline forwards an optional system message to every request."""
    seen = []

    class Recording(ReasoningProvider):
        name = "recording"

        def generate(self, *, system, prompt, context, output_type):
            seen.append(system)
            return TextOutput(answer="ok")

    pipeline = ExperimentPipeline(
        ExperimentRunner(Recording()), EvaluationFramework([ResponseEvaluator()])
    )
    pipeline.run(_dataset(), output_type=TextOutput, system="Be concise.")
    assert seen == ["Be concise.", "Be concise."]


def test_all_cases_unexpectedly_failing():
    """Total collapse yields failures only and no report, without raising."""
    runner = ExperimentRunner(StubProvider())
    original = runner.run

    def broken(request, *, output_type):
        raise RuntimeError("kaput")

    runner.run = broken
    pipeline = ExperimentPipeline(runner, EvaluationFramework([ResponseEvaluator()]))
    result = pipeline.run(_dataset(), output_type=TextOutput)
    assert result.records == []
    assert len(result.failures) == 2
    assert all(failure.stage == "run" for failure in result.failures)
    assert result.report is None


def test_aggregation_bug_surfaces_loudly():
    """An aggregation crash propagates instead of forging an empty report."""
    import axiom.pipeline.pipeline as pipeline_module

    original = pipeline_module.aggregate_benchmark

    def broken(benchmark, records, *, label=""):
        raise RuntimeError("aggregate kaput")

    pipeline_module.aggregate_benchmark = broken
    try:
        pipeline = _pipeline()
        try:
            pipeline.run(_dataset(), output_type=TextOutput)
        except RuntimeError as exc:
            assert "aggregate kaput" in str(exc)
            return
        raise AssertionError("expected RuntimeError")
    finally:
        pipeline_module.aggregate_benchmark = original


def test_mixed_provider_outcomes_visible_in_report():
    """One failed and one completed experiment share a report honestly."""
    class SelectiveProvider(StubProvider):
        """Test double failing only the second benchmark case."""

        def generate(self, *, system, prompt, context, output_type):
            """Raise for the second case, answer everything else."""
            if "Second" in prompt:
                raise ProviderError("down")
            return super().generate(
                system=system, prompt=prompt, context=context, output_type=output_type
            )

    pipeline = _pipeline(provider=SelectiveProvider())
    result = pipeline.run(_dataset(), output_type=TextOutput)
    assert len(result.records) == 2
    assert result.failures == []
    assert result.report is not None
    response = result.report.summary_for("response")
    assert response is not None
    assert response.passed == 1
    assert response.failed == 1
