"""Comparison engine: read-only diffs of two benchmark runs."""

from __future__ import annotations

from axiom.domain.models import Direction, utcnow
from axiom.comparison.models import (
    CaseComparison,
    MetadataDifference,
    MetricDelta,
    MetricVerdict,
    RunComparison,
)
from axiom.runs.models import BenchmarkRun

KNOWN_DIRECTIONS: dict[str, Direction] = {
    "accuracy": Direction.MAXIMIZE,
    "score": Direction.MAXIMIZE,
    "success_rate": Direction.MAXIMIZE,
    "throughput": Direction.MAXIMIZE,
    "latency": Direction.MINIMIZE,
    "latency_ms": Direction.MINIMIZE,
    "token_usage": Direction.MINIMIZE,
    "tokens": Direction.MINIMIZE,
    "total_tokens": Direction.MINIMIZE,
    "error_count": Direction.MINIMIZE,
    "errors": Direction.MINIMIZE,
}

METADATA_FIELDS = (
    "dataset_version",
    "label",
    "system",
    "output_schema",
    "providers",
    "models",
    "evaluator_names",
    "max_concurrency",
    "fail_fast",
    "seed",
    "temperature",
    "top_p",
    "max_tokens",
)


class IncompatibleRunsError(ValueError):
    """Raised when two runs cannot be meaningfully compared."""


def compare_metric(
    metric: str,
    value_a: float | None,
    value_b: float | None,
    direction: Direction | None,
) -> MetricDelta:
    """Diff two measurements with direction-aware verdict and safe percent."""
    delta: float | None = None
    percent: float | None = None
    verdict = MetricVerdict.UNKNOWN
    if value_a is not None and value_b is not None:
        delta = value_b - value_a
        if value_a != 0:
            percent = delta / abs(value_a) * 100.0
        if delta == 0:
            verdict = MetricVerdict.UNCHANGED
        elif direction is not None:
            better = delta > 0
            wants_up = direction == Direction.MAXIMIZE
            verdict = MetricVerdict.IMPROVED if better == wants_up else MetricVerdict.REGRESSED
    return MetricDelta(
        metric=metric,
        value_a=value_a,
        value_b=value_b,
        delta=delta,
        percent=percent,
        direction=direction,
        verdict=verdict,
    )


def compare_runs(
    run_a: BenchmarkRun,
    run_b: BenchmarkRun,
    *,
    directions: dict[str, Direction] | None = None,
) -> RunComparison:
    """Compare two runs of one benchmark without modifying either."""
    if not isinstance(run_a, BenchmarkRun) or not isinstance(run_b, BenchmarkRun):
        raise TypeError(
            "Expected BenchmarkRun inputs, "
            f"got {type(run_a).__name__} and {type(run_b).__name__}"
        )
    if run_a.config.dataset != run_b.config.dataset:
        raise IncompatibleRunsError(
            f"Cannot compare {run_a.config.dataset!r} with {run_b.config.dataset!r}"
        )
    known = dict(KNOWN_DIRECTIONS)
    if directions:
        known.update(directions)
    warnings: list[str] = []
    metadata = _compare_metadata(run_a, run_b)
    metrics = _compare_aggregates(run_a, run_b, known, warnings)
    cases, missing_in_b, missing_in_a = _compare_cases(run_a, run_b, known, warnings)
    return RunComparison(
        run_a_id=run_a.id,
        run_b_id=run_b.id,
        benchmark=run_a.config.dataset,
        dataset_version=run_a.config.dataset_version,
        label_a=run_a.config.label,
        label_b=run_b.config.label,
        providers_a=list(run_a.config.providers),
        providers_b=list(run_b.config.providers),
        models_a=list(run_a.config.models),
        models_b=list(run_b.config.models),
        metadata_differences=metadata,
        metrics=metrics,
        cases=cases,
        missing_in_b=missing_in_b,
        missing_in_a=missing_in_a,
        warnings=warnings,
        compared_at=utcnow(),
    )


def _compare_metadata(run_a: BenchmarkRun, run_b: BenchmarkRun) -> list[MetadataDifference]:
    """List configuration fields whose values differ, without judging them."""
    config_a = run_a.config.model_dump()
    config_b = run_b.config.model_dump()
    differences = []
    for field in METADATA_FIELDS:
        if config_a[field] != config_b[field]:
            differences.append(
                MetadataDifference(field=field, value_a=config_a[field], value_b=config_b[field])
            )
    return differences


def _means_by_evaluator(run: BenchmarkRun) -> dict[str, float | None]:
    """Aggregate means per evaluator from the stored report, if any."""
    if run.report is None:
        return {}
    return {summary.evaluator: summary.mean for summary in run.report.summaries}


def _compare_aggregates(
    run_a: BenchmarkRun,
    run_b: BenchmarkRun,
    known: dict[str, Direction],
    warnings: list[str],
) -> list[MetricDelta]:
    """Diff report means, flagging missing metrics and unknown directions."""
    means_a = _means_by_evaluator(run_a)
    means_b = _means_by_evaluator(run_b)
    if run_a.report is None or run_b.report is None:
        warnings.append("Aggregate comparison skipped: a run has no stored report")
        return []
    deltas = []
    for metric in list(means_a) + [name for name in means_b if name not in means_a]:
        direction = known.get(metric)
        if direction is None:
            warnings.append(f"No direction known for metric {metric!r}; verdict unknown")
        if metric not in means_a or metric not in means_b:
            warnings.append(f"Metric {metric!r} missing on one side")
        deltas.append(compare_metric(metric, means_a.get(metric), means_b.get(metric), direction))
    return deltas


def _outcomes_by_name(record) -> dict[str, float | None]:
    """Map evaluator names to scores for one case record."""
    return {outcome.evaluator: outcome.score for outcome in record.evaluation.outcomes}


def _compare_cases(
    run_a: BenchmarkRun,
    run_b: BenchmarkRun,
    known: dict[str, Direction],
    warnings: list[str],
) -> tuple[list[CaseComparison], list[str], list[str]]:
    """Match records by stable case ID and diff shared cases metric by metric."""
    records_a = {record.case_id: record for record in run_a.records}
    records_b = {record.case_id: record for record in run_b.records}
    missing_in_b = [case_id for case_id in records_a if case_id not in records_b]
    missing_in_a = [case_id for case_id in records_b if case_id not in records_a]
    comparisons = []
    for case_id in records_a:
        if case_id not in records_b:
            comparisons.append(CaseComparison(case_id=case_id, present_a=True, present_b=False))
            continue
        scores_a = _outcomes_by_name(records_a[case_id])
        scores_b = _outcomes_by_name(records_b[case_id])
        metrics = []
        for metric in list(scores_a) + [name for name in scores_b if name not in scores_a]:
            metrics.append(
                compare_metric(metric, scores_a.get(metric), scores_b.get(metric), known.get(metric))
            )
        comparisons.append(
            CaseComparison(case_id=case_id, present_a=True, present_b=True, metrics=metrics)
        )
    for case_id in missing_in_a:
        comparisons.append(CaseComparison(case_id=case_id, present_a=False, present_b=True))
    return comparisons, missing_in_b, missing_in_a
