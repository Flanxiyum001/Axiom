"""Aggregation: grouping, statistics, comparison, and text rendering."""

from axiom.evaluation.models import EvaluationResult, EvaluatorOutcome
from axiom.experiments.runner import ExperimentResult
from axiom.reporting.aggregation import (
    AggregationError,
    aggregate_benchmark,
    compare_reports,
    format_text,
)
from axiom.reporting.models import CaseRecord


def _record(case_id, score, passed=True, evaluator="accuracy"):
    """Pair one experiment result with one evaluation outcome."""
    experiment = ExperimentResult(status="completed", latency_ms=100.0, provider="stub")
    evaluation = EvaluationResult(
        experiment=experiment,
        outcomes=[EvaluatorOutcome(evaluator=evaluator, passed=passed, score=score)],
    )
    return CaseRecord(case_id=case_id, experiment=experiment, evaluation=evaluation)


def test_aggregates_mean_min_max_count():
    """Scores group by evaluator with correct summary statistics."""
    report = aggregate_benchmark(
        "example_benchmark",
        [_record("c1", 1.0), _record("c2", 0.0), _record("c3", 1.0)],
    )
    assert report.cases == 3
    summary = report.summary_for("accuracy")
    assert summary is not None
    assert summary.scored == 3
    assert abs(summary.mean - 0.6666667) < 1e-6
    assert summary.min == 0.0
    assert summary.max == 1.0


def test_verdict_counts_tracked_per_evaluator():
    """Pass, fail, and inconclusive tallies accumulate independently."""
    report = aggregate_benchmark(
        "bench",
        [
            _record("c1", 1.0, passed=True),
            _record("c2", 0.0, passed=False),
            _record("c3", None, passed=None),
        ],
    )
    summary = report.summary_for("accuracy")
    assert summary is not None
    assert (summary.passed, summary.failed, summary.inconclusive) == (1, 1, 1)
    assert summary.scored == 2


def test_unscored_evaluator_has_empty_statistics():
    """Evaluators with no scores report counts but no statistics."""
    report = aggregate_benchmark("bench", [_record("c1", None, passed=None)])
    summary = report.summary_for("accuracy")
    assert summary is not None
    assert summary.scored == 0
    assert summary.mean is None
    assert summary.min is None
    assert summary.max is None


def test_non_finite_scores_skipped():
    """NaN and infinite scores never poison aggregated statistics."""
    report = aggregate_benchmark(
        "bench",
        [_record("c1", float("nan")), _record("c2", float("inf")), _record("c3", 4.0)],
    )
    summary = report.summary_for("accuracy")
    assert summary is not None
    assert summary.scored == 1
    assert summary.mean == 4.0


def test_records_preserved_and_input_untouched():
    """Every record survives aggregation; source objects stay identical."""
    records = [_record("c1", 1.0), _record("c2", 0.0)]
    before = [record.model_dump_json() for record in records]
    report = aggregate_benchmark("bench", records, label="run-a")
    assert report.label == "run-a"
    assert [record.case_id for record in report.records] == ["c1", "c2"]
    assert [record.model_dump_json() for record in records] == before


def test_empty_records_rejected():
    """Aggregating nothing fails loudly instead of emitting an empty report."""
    try:
        aggregate_benchmark("bench", [])
    except AggregationError:
        return
    raise AssertionError("expected AggregationError")


def test_blank_benchmark_name_rejected():
    """Reports always carry the benchmark they group."""
    try:
        aggregate_benchmark("  ", [_record("c1", 1.0)])
    except AggregationError:
        return
    raise AssertionError("expected AggregationError")


def test_compare_reports_mean_shift():
    """Shared evaluators compare by mean delta from baseline to candidate."""
    baseline = aggregate_benchmark("bench", [_record("c1", 500.0), _record("c2", 700.0)], label="a")
    candidate = aggregate_benchmark("bench", [_record("c1", 400.0), _record("c2", 400.0)], label="b")
    comparison = compare_reports(baseline, candidate)
    assert comparison.baseline_label == "a"
    assert comparison.candidate_label == "b"
    assert len(comparison.comparisons) == 1
    metric = comparison.comparisons[0]
    assert metric.evaluator == "accuracy"
    assert metric.baseline_mean == 600.0
    assert metric.candidate_mean == 400.0
    assert metric.delta == -200.0


def test_compare_skips_unshared_evaluators():
    """Evaluators present on only one side never produce phantom deltas."""
    baseline = aggregate_benchmark("bench", [_record("c1", 1.0, evaluator="accuracy")])
    candidate = aggregate_benchmark("bench", [_record("c1", 5.0, evaluator="latency")])
    assert compare_reports(baseline, candidate).comparisons == []


def test_compare_unscored_means_yield_no_delta():
    """Missing means compare as unknown rather than zero shift."""
    baseline = aggregate_benchmark("bench", [_record("c1", None, passed=None)])
    candidate = aggregate_benchmark("bench", [_record("c1", None, passed=None)])
    (metric,) = compare_reports(baseline, candidate).comparisons
    assert metric.delta is None


def test_format_text_matches_canonical_shape():
    """Rendered reports follow the documented benchmark format."""
    report = aggregate_benchmark(
        "example_benchmark",
        [_record("c1", 1.0), _record("c2", 0.0), _record("c3", 1.0)],
    )
    text = format_text(report)
    assert "Benchmark: example_benchmark" in text
    assert "Cases: 3" in text
    assert "accuracy:" in text
    assert "Mean: 0.67" in text
    assert "Min: 0.00" in text
    assert "Max: 1.00" in text


def test_format_text_marks_unscored_metrics():
    """Metrics without scores render explicitly instead of misleading zeros."""
    report = aggregate_benchmark("bench", [_record("c1", None, passed=None)])
    assert "Mean: n/a" in format_text(report)


def test_summary_for_missing_evaluator():
    """Unknown evaluator lookup returns None instead of raising."""
    report = aggregate_benchmark("bench", [_record("c1", 1.0)])
    assert report.summary_for("nope") is None
