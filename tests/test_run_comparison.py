"""Run comparison: deltas, verdicts, case matching, incompatibility."""

from axiom.comparison.comparison import (
    IncompatibleRunsError,
    compare_metric,
    compare_runs,
)
from axiom.comparison.models import MetricVerdict
from axiom.domain.models import Direction
from axiom.evaluation.models import EvaluationResult, EvaluatorOutcome
from axiom.experiments.runner import ExperimentResult
from axiom.reporting.aggregation import aggregate_benchmark
from axiom.reporting.models import CaseRecord
from axiom.runs.models import BenchmarkRun, ExecutionConfig


def _record(case_id, outcomes):
    """Pair one experiment with evaluation outcomes for comparison tests."""
    experiment = ExperimentResult(status="completed", latency_ms=100.0, provider="stub")
    evaluation = EvaluationResult(
        experiment=experiment,
        outcomes=[EvaluatorOutcome(evaluator=name, passed=True, score=score) for name, score in outcomes],
    )
    return CaseRecord(case_id=case_id, experiment=experiment, evaluation=evaluation)


def _run(dataset="bench", cases=None, config=None, label=""):
    """Aggregate records into a stored run with overridable configuration."""
    records = cases if cases is not None else []
    report = aggregate_benchmark(dataset, records) if records else None
    settings = {"dataset": dataset, "label": label}
    settings.update(config or {})
    return BenchmarkRun(config=ExecutionConfig(**settings), records=records, report=report)


def test_basic_comparison_generates_result():
    """Two runs of one benchmark compare with identifiers linked."""
    first = _run(cases=[_record("c1", [("accuracy", 0.8)])])
    second = _run(cases=[_record("c1", [("accuracy", 0.9)])])
    comparison = compare_runs(first, second)
    assert comparison.run_a_id == first.id
    assert comparison.run_b_id == second.id
    assert comparison.benchmark == "bench"


def test_absolute_and_percentage_differences():
    """Deltas subtract B minus A with percentages against the baseline."""
    delta = compare_metric("accuracy", 80.0, 88.0, Direction.MAXIMIZE)
    assert delta.delta == 8.0
    assert delta.percent == 10.0
    delta = compare_metric("latency_ms", 500.0, 400.0, Direction.MINIMIZE)
    assert delta.delta == -100.0
    assert delta.percent == -20.0


def test_direction_maximize_improved_and_regressed():
    """Higher-better metrics improve upward and regress downward."""
    assert compare_metric("accuracy", 80.0, 90.0, Direction.MAXIMIZE).verdict == MetricVerdict.IMPROVED
    assert compare_metric("accuracy", 90.0, 80.0, Direction.MAXIMIZE).verdict == MetricVerdict.REGRESSED
    assert compare_metric("accuracy", 80.0, 80.0, Direction.MAXIMIZE).verdict == MetricVerdict.UNCHANGED


def test_direction_minimize_improved_and_regressed():
    """Lower-better metrics improve downward and regress upward."""
    assert compare_metric("latency_ms", 500.0, 400.0, Direction.MINIMIZE).verdict == MetricVerdict.IMPROVED
    assert compare_metric("latency_ms", 400.0, 500.0, Direction.MINIMIZE).verdict == MetricVerdict.REGRESSED
    assert compare_metric("latency_ms", 500.0, 500.0, Direction.MINIMIZE).verdict == MetricVerdict.UNCHANGED


def test_unknown_direction_stays_unknown():
    """Metrics without direction never guess a verdict."""
    delta = compare_metric("mystery", 1.0, 2.0, None)
    assert delta.verdict == MetricVerdict.UNKNOWN
    assert delta.delta == 1.0


def test_zero_values_never_divide():
    """Zero baselines skip percentages while deltas and verdicts stay valid."""
    up = compare_metric("accuracy", 0.0, 10.0, Direction.MAXIMIZE)
    assert up.delta == 10.0
    assert up.percent is None
    assert up.verdict == MetricVerdict.IMPROVED
    down = compare_metric("accuracy", 10.0, 0.0, Direction.MAXIMIZE)
    assert down.delta == -10.0
    assert down.percent == -100.0
    assert down.verdict == MetricVerdict.REGRESSED
    flat = compare_metric("accuracy", 0.0, 0.0, Direction.MAXIMIZE)
    assert flat.delta == 0.0
    assert flat.percent is None
    assert flat.verdict == MetricVerdict.UNCHANGED


def test_case_level_improved_regressed_unchanged():
    """Shared cases classify per metric from their own scores."""
    first = _run(
        cases=[
            _record("up", [("score", 0.0)]),
            _record("down", [("score", 1.0)]),
            _record("same", [("score", 1.0)]),
        ]
    )
    second = _run(
        cases=[
            _record("up", [("score", 1.0)]),
            _record("down", [("score", 0.0)]),
            _record("same", [("score", 1.0)]),
        ]
    )
    by_id = {case.case_id: case for case in compare_runs(first, second).cases}
    assert by_id["up"].metrics[0].verdict == MetricVerdict.IMPROVED
    assert by_id["down"].metrics[0].verdict == MetricVerdict.REGRESSED
    assert by_id["same"].metrics[0].verdict == MetricVerdict.UNCHANGED


def test_missing_cases_reported_both_ways():
    """Cases absent on either side are listed, never silently dropped."""
    first = _run(cases=[_record("c1", [("score", 1.0)]), _record("c2", [("score", 1.0)])])
    second = _run(cases=[_record("c1", [("score", 1.0)]), _record("c3", [("score", 1.0)])])
    comparison = compare_runs(first, second)
    assert comparison.missing_in_b == ["c2"]
    assert comparison.missing_in_a == ["c3"]
    by_id = {case.case_id: case for case in comparison.cases}
    assert by_id["c2"].present_a and not by_id["c2"].present_b
    assert by_id["c2"].metrics == []
    assert not by_id["c3"].present_a and by_id["c3"].present_b


def test_incompatible_benchmarks_rejected():
    """Different datasets refuse comparison with a named explanation."""
    first = _run(dataset="bench-a", cases=[_record("c1", [("score", 1.0)])])
    second = _run(dataset="bench-b", cases=[_record("c1", [("score", 1.0)])])
    try:
        compare_runs(first, second)
    except IncompatibleRunsError as exc:
        assert "bench-a" in str(exc) and "bench-b" in str(exc)
        return
    raise AssertionError("expected IncompatibleRunsError")


def test_invalid_inputs_rejected():
    """Non-run inputs fail with a type error instead of comparing."""
    run = _run(cases=[_record("c1", [("score", 1.0)])])
    for bad in (None, {}, "run"):
        try:
            compare_runs(run, bad)
        except TypeError:
            continue
        raise AssertionError(f"expected TypeError for {bad!r}")


def test_missing_metrics_reported():
    """Metrics absent on one side stay unknown with a warning attached."""
    first = _run(cases=[_record("c1", [("accuracy", 0.8), ("latency_ms", 500.0)])])
    second = _run(cases=[_record("c1", [("accuracy", 0.9)])])
    comparison = compare_runs(first, second)
    by_metric = {metric.metric: metric for metric in comparison.metrics}
    assert by_metric["accuracy"].verdict == MetricVerdict.IMPROVED
    assert by_metric["latency_ms"].value_b is None
    assert by_metric["latency_ms"].verdict == MetricVerdict.UNKNOWN
    assert any("latency_ms" in warning for warning in comparison.warnings)


def test_multiple_metrics_compared_independently():
    """Accuracy, latency, and token metrics each get their own verdict."""
    first = _run(cases=[_record("c1", [("accuracy", 0.82), ("latency_ms", 450.0), ("total_tokens", 1200.0)])])
    second = _run(cases=[_record("c1", [("accuracy", 0.87), ("latency_ms", 520.0), ("total_tokens", 1050.0)])])
    by_metric = {metric.metric: metric for metric in compare_runs(first, second).metrics}
    assert by_metric["accuracy"].verdict == MetricVerdict.IMPROVED
    assert by_metric["latency_ms"].verdict == MetricVerdict.REGRESSED
    assert by_metric["total_tokens"].verdict == MetricVerdict.IMPROVED


def test_metadata_differences_represented():
    """Model, provider, and config differences show without verdicts."""
    first = _run(
        config={"providers": ["p1"], "models": ["m1"], "temperature": 0.2, "label": "a"},
        cases=[_record("c1", [("score", 1.0)])],
    )
    second = _run(
        config={"providers": ["p2"], "models": ["m1"], "temperature": 0.7, "label": "b"},
        cases=[_record("c1", [("score", 1.0)])],
    )
    comparison = compare_runs(first, second)
    by_field = {item.field: item for item in comparison.metadata_differences}
    assert by_field["providers"].value_a == ["p1"]
    assert by_field["providers"].value_b == ["p2"]
    assert by_field["temperature"].value_a == 0.2
    assert "models" not in by_field
    assert comparison.providers_a == ["p1"]
    assert comparison.models_b == ["m1"]


def test_custom_directions_override_defaults():
    """Callers can teach the engine directions for custom metrics."""
    first = _run(cases=[_record("c1", [("vibes", 1.0)])])
    second = _run(cases=[_record("c1", [("vibes", 2.0)])])
    assert compare_runs(first, second).metrics[0].verdict == MetricVerdict.UNKNOWN
    assert (
        compare_runs(first, second, directions={"vibes": Direction.MAXIMIZE}).metrics[0].verdict
        == MetricVerdict.IMPROVED
    )


def test_comparison_leaves_inputs_untouched():
    """Comparing never mutates either run or its nested results."""
    first = _run(cases=[_record("c1", [("accuracy", 0.8)])])
    second = _run(cases=[_record("c1", [("accuracy", 0.9)])])
    before_a, before_b = first.model_dump_json(), second.model_dump_json()
    compare_runs(first, second)
    assert first.model_dump_json() == before_a
    assert second.model_dump_json() == before_b
