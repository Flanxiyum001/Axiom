"""Regression detection: statuses, thresholds, cases, boundaries, immutability."""

from axiom.comparison.comparison import compare_runs
from axiom.evaluation.models import EvaluationResult, EvaluatorOutcome
from axiom.experiments.runner import ExperimentResult
from axiom.regression.detection import detect_from_comparison, detect_regressions
from axiom.regression.models import MetricThresholds, RegressionConfig, RegressionStatus
from axiom.reporting.aggregation import aggregate_benchmark
from axiom.reporting.models import CaseRecord
from axiom.runs.models import BenchmarkRun, ExecutionConfig


def _record(case_id, outcomes):
    """Pair one experiment with evaluation outcomes for regression tests."""
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


def _pct_config(warn, fail):
    """Default percentage thresholds applied to every metric."""
    return RegressionConfig(default_warn_pct=warn, default_fail_pct=fail)


def test_no_regression_passes():
    """Equivalent performance yields PASS."""
    baseline = _run(cases=[_record("c1", [("accuracy", 0.9)])])
    candidate = _run(cases=[_record("c1", [("accuracy", 0.9)])])
    report = detect_regressions(baseline, candidate, _pct_config(2.0, 5.0))
    assert report.status == RegressionStatus.PASS


def test_warning_regression():
    """Accuracy 90 -> 87 exceeds warn 2% but not fail 5%."""
    baseline = _run(cases=[_record("c1", [("accuracy", 90.0)])])
    candidate = _run(cases=[_record("c1", [("accuracy", 87.0)])])
    report = detect_regressions(baseline, candidate, _pct_config(2.0, 5.0))
    assert report.status == RegressionStatus.WARNING
    assert report.metrics[0].status == RegressionStatus.WARNING


def test_failure_regression():
    """Accuracy 90 -> 82 exceeds fail 5%."""
    baseline = _run(cases=[_record("c1", [("accuracy", 90.0)])])
    candidate = _run(cases=[_record("c1", [("accuracy", 82.0)])])
    report = detect_regressions(baseline, candidate, _pct_config(2.0, 5.0))
    assert report.status == RegressionStatus.FAIL


def test_higher_is_better_decrease_regresses():
    """Accuracy drops are regressions; symmetric config, direction decides."""
    baseline = _run(cases=[_record("c1", [("accuracy", 0.9)])])
    candidate = _run(cases=[_record("c1", [("accuracy", 0.8)])])
    report = detect_regressions(baseline, candidate, RegressionConfig())
    assert report.status == RegressionStatus.WARNING


def test_lower_is_better_increase_regresses():
    """Latency increases are regressions."""
    baseline = _run(cases=[_record("c1", [("latency_ms", 400.0)])])
    candidate = _run(cases=[_record("c1", [("latency_ms", 470.0)])])
    report = detect_regressions(baseline, candidate, _pct_config(10.0, 20.0))
    assert report.status == RegressionStatus.WARNING


def test_improvement_never_regresses():
    """Better accuracy and lower latency stay PASS."""
    baseline = _run(cases=[_record("c1", [("accuracy", 0.8)])])
    candidate = _run(cases=[_record("c1", [("accuracy", 0.9)])])
    assert detect_regressions(baseline, candidate, _pct_config(2.0, 5.0)).status == RegressionStatus.PASS
    slow = _run(cases=[_record("c1", [("latency_ms", 500.0)])])
    fast = _run(cases=[_record("c1", [("latency_ms", 400.0)])])
    assert detect_regressions(slow, fast, _pct_config(10.0, 20.0)).status == RegressionStatus.PASS


def test_unchanged_metric_passes():
    """Identical metrics remain PASS."""
    baseline = _run(cases=[_record("c1", [("accuracy", 0.9)])])
    candidate = _run(cases=[_record("c1", [("accuracy", 0.9)])])
    report = detect_regressions(baseline, candidate, _pct_config(2.0, 5.0))
    assert report.metrics[0].status == RegressionStatus.PASS


def test_case_level_regressions():
    """Shared cases classify regressed, improved, and unchanged separately."""
    baseline = _run(
        cases=[
            _record("down", [("score", 1.0)]),
            _record("up", [("score", 0.0)]),
            _record("same", [("score", 1.0)]),
        ]
    )
    candidate = _run(
        cases=[
            _record("down", [("score", 0.0)]),
            _record("up", [("score", 1.0)]),
            _record("same", [("score", 1.0)]),
        ]
    )
    by_id = {case.case_id: case for case in detect_regressions(baseline, candidate).cases}
    assert by_id["down"].status == RegressionStatus.WARNING
    assert by_id["up"].status == RegressionStatus.PASS
    assert by_id["same"].status == RegressionStatus.PASS


def test_missing_cases_reported():
    """Baseline-only cases warn; candidate-only cases stay informational."""
    baseline = _run(cases=[_record("c1", [("score", 1.0)]), _record("c2", [("score", 1.0)])])
    candidate = _run(cases=[_record("c1", [("score", 1.0)]), _record("c3", [("score", 1.0)])])
    report = detect_regressions(baseline, candidate)
    assert report.missing_in_candidate == ["c2"]
    assert report.missing_in_baseline == ["c3"]
    by_id = {case.case_id: case for case in report.cases}
    assert by_id["c2"].status == RegressionStatus.WARNING
    assert by_id["c3"].status == RegressionStatus.PASS
    assert report.status == RegressionStatus.WARNING


def test_multiple_metrics_overall_status():
    """Overall status is the worst across metrics."""
    baseline = _run(cases=[_record("c1", [("accuracy", 90.0), ("latency_ms", 400.0)])])
    candidate = _run(cases=[_record("c1", [("accuracy", 87.0), ("latency_ms", 500.0)])])
    config = RegressionConfig(
        per_metric={
            "accuracy": MetricThresholds(warn_pct=2.0, fail_pct=5.0),
            "latency_ms": MetricThresholds(warn_pct=10.0, fail_pct=20.0),
        }
    )
    assert detect_regressions(baseline, candidate, config).status == RegressionStatus.FAIL


def test_overall_status_combinations():
    """PASS/WARNING/FAIL combine deterministically via worst-wins."""
    assert detect_regressions(
        _run(cases=[_record("c1", [("accuracy", 90.0)])]),
        _run(cases=[_record("c1", [("accuracy", 89.9)])]),
        _pct_config(2.0, 5.0),
    ).status == RegressionStatus.PASS
    assert detect_regressions(
        _run(cases=[_record("c1", [("accuracy", 90.0)])]),
        _run(cases=[_record("c1", [("accuracy", 87.0)])]),
        _pct_config(2.0, 5.0),
    ).status == RegressionStatus.WARNING
    assert detect_regressions(
        _run(cases=[_record("c1", [("accuracy", 90.0)])]),
        _run(cases=[_record("c1", [("accuracy", 82.0)])]),
        _pct_config(2.0, 5.0),
    ).status == RegressionStatus.FAIL


def test_threshold_boundaries_inclusive():
    """Magnitudes at the threshold trigger; just below does not."""
    baseline = _run(cases=[_record("c1", [("accuracy", 100.0)])])
    below = _run(cases=[_record("c1", [("accuracy", 98.01)])])
    exact = _run(cases=[_record("c1", [("accuracy", 98.0)])])
    above = _run(cases=[_record("c1", [("accuracy", 97.99)])])
    config = RegressionConfig(default_warn_pct=2.0)
    assert detect_regressions(baseline, below, config).status == RegressionStatus.PASS
    assert detect_regressions(baseline, exact, config).status == RegressionStatus.WARNING
    assert detect_regressions(baseline, above, config).status == RegressionStatus.WARNING


def test_absolute_thresholds_supported():
    """Absolute deltas trigger independently of percentages."""
    baseline = _run(cases=[_record("c1", [("latency_ms", 400.0)])])
    candidate = _run(cases=[_record("c1", [("latency_ms", 420.0)])])
    config = RegressionConfig(default_warn_abs=10.0, default_fail_abs=50.0)
    assert detect_regressions(baseline, candidate, config).status == RegressionStatus.WARNING
    worse = _run(cases=[_record("c1", [("latency_ms", 460.0)])])
    assert detect_regressions(baseline, worse, config).status == RegressionStatus.FAIL


def test_zero_baseline_safe():
    """Zero baselines use absolute thresholds without division errors."""
    baseline = _run(cases=[_record("c1", [("score", 0.0)])])
    candidate = _run(cases=[_record("c1", [("score", 0.0)])])
    assert detect_regressions(baseline, candidate, _pct_config(2.0, 5.0)).status == RegressionStatus.PASS
    nonzero = _run(cases=[_record("c1", [("score", 1.0)])])
    report = detect_regressions(nonzero, baseline, _pct_config(2.0, 5.0))
    assert report.status in (RegressionStatus.WARNING, RegressionStatus.FAIL)


def test_zero_baseline_percentage_only_warns():
    """Zero baselines have no percent, so pct-only thresholds cannot pass a regression."""
    baseline = _run(cases=[_record("c1", [("latency_ms", 0.0)])])
    candidate = _run(cases=[_record("c1", [("latency_ms", 50.0)])])
    report = detect_regressions(baseline, candidate, _pct_config(2.0, 5.0))
    assert report.metrics[0].percent is None
    assert report.status == RegressionStatus.WARNING


def test_negative_thresholds_rejected():
    """Negative thresholds are invalid and rejected before evaluation."""
    for bad in (
        MetricThresholds,
        RegressionConfig,
    ):
        try:
            if bad is MetricThresholds:
                bad(warn_abs=-1.0)
            else:
                bad(default_fail_abs=-1.0)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad.__name__}")


def test_detection_leaves_inputs_untouched():
    """Detection never mutates runs or the comparison result."""
    baseline = _run(cases=[_record("c1", [("accuracy", 0.9)])])
    candidate = _run(cases=[_record("c1", [("accuracy", 0.8)])])
    comparison = compare_runs(baseline, candidate)
    before_runs = (baseline.model_dump_json(), candidate.model_dump_json())
    before_comparison = comparison.model_dump_json()
    detect_from_comparison(comparison, _pct_config(2.0, 5.0))
    assert baseline.model_dump_json() == before_runs[0]
    assert candidate.model_dump_json() == before_runs[1]
    assert comparison.model_dump_json() == before_comparison


def test_accepts_existing_comparison_result():
    """The detector consumes a prebuilt comparison without recomparing."""
    baseline = _run(cases=[_record("c1", [("accuracy", 90.0)])])
    candidate = _run(cases=[_record("c1", [("accuracy", 82.0)])])
    comparison = compare_runs(baseline, candidate)
    report = detect_from_comparison(comparison, _pct_config(2.0, 5.0))
    assert report.baseline_run_id == baseline.id
    assert report.candidate_run_id == candidate.id
    assert report.status == RegressionStatus.FAIL
