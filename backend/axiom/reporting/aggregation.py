"""Aggregation: group case records into summaries, compare reports, render text."""

from __future__ import annotations

import math
from collections import defaultdict

from axiom.domain.models import utcnow
from axiom.reporting.models import (
    BenchmarkReport,
    CaseRecord,
    ComparisonReport,
    EvaluatorSummary,
    MetricComparison,
)


class AggregationError(ValueError):
    """Raised when records cannot form a meaningful report."""


def aggregate_benchmark(
    benchmark: str,
    records: list[CaseRecord],
    *,
    label: str = "",
) -> BenchmarkReport:
    """Group one benchmark's records into per-evaluator summaries."""
    if not benchmark.strip():
        raise AggregationError("Benchmark name must not be blank")
    if not records:
        raise AggregationError("Cannot aggregate zero records")
    scores: dict[str, list[float]] = defaultdict(list)
    summaries: dict[str, EvaluatorSummary] = {}
    for record in records:
        for outcome in record.evaluation.outcomes:
            summary = summaries.get(outcome.evaluator)
            if summary is None:
                summary = EvaluatorSummary(evaluator=outcome.evaluator)
                summaries[outcome.evaluator] = summary
            if outcome.passed is True:
                summary.passed += 1
            elif outcome.passed is False:
                summary.failed += 1
            else:
                summary.inconclusive += 1
            if outcome.score is not None and math.isfinite(outcome.score):
                scores[outcome.evaluator].append(outcome.score)
    ordered = [summaries[name] for name in summaries]
    for summary in ordered:
        values = scores[summary.evaluator]
        summary.scored = len(values)
        if values:
            summary.mean = sum(values) / len(values)
            summary.min = min(values)
            summary.max = max(values)
    return BenchmarkReport(
        benchmark=benchmark,
        label=label,
        cases=len(records),
        summaries=ordered,
        records=list(records),
        generated_at=utcnow(),
    )


def compare_reports(baseline: BenchmarkReport, candidate: BenchmarkReport) -> ComparisonReport:
    """Compare shared evaluators by mean shift from baseline to candidate."""
    comparisons: list[MetricComparison] = []
    for candidate_summary in candidate.summaries:
        baseline_summary = baseline.summary_for(candidate_summary.evaluator)
        if baseline_summary is None:
            continue
        delta = None
        if baseline_summary.mean is not None and candidate_summary.mean is not None:
            delta = candidate_summary.mean - baseline_summary.mean
        comparisons.append(
            MetricComparison(
                evaluator=candidate_summary.evaluator,
                baseline_mean=baseline_summary.mean,
                candidate_mean=candidate_summary.mean,
                delta=delta,
            )
        )
    return ComparisonReport(
        baseline_label=baseline.label,
        candidate_label=candidate.label,
        comparisons=comparisons,
        generated_at=utcnow(),
    )


def format_text(report: BenchmarkReport) -> str:
    """Render a report in the canonical human-readable benchmark format."""
    lines = [
        f"Benchmark: {report.benchmark}",
        f"Cases: {report.cases}",
        "",
    ]
    for summary in report.summaries:
        lines.append(f"{summary.evaluator}:")
        lines.append(f"  Mean: {_format_number(summary.mean)}")
        lines.append(f"  Min: {_format_number(summary.min)}")
        lines.append(f"  Max: {_format_number(summary.max)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _format_number(value: float | None) -> str:
    """Render a summary statistic, marking unscored metrics explicitly."""
    if value is None:
        return "n/a"
    return f"{value:.2f}"
