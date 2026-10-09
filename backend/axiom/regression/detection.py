"""Regression detection: evaluate a run comparison against thresholds."""

from __future__ import annotations

from axiom.comparison.comparison import compare_runs
from axiom.comparison.models import MetricDelta, MetricVerdict, RunComparison
from axiom.domain.models import utcnow
from axiom.regression.models import (
    CaseRegression,
    MetricRegression,
    RegressionConfig,
    RegressionReport,
    RegressionStatus,
)
from axiom.runs.models import BenchmarkRun

_STATUS_ORDER = {
    RegressionStatus.PASS: 0,
    RegressionStatus.WARNING: 1,
    RegressionStatus.FAIL: 2,
}


def _worst(statuses: list[RegressionStatus]) -> RegressionStatus:
    """Return the most severe status, defaulting to PASS."""
    result = RegressionStatus.PASS
    for status in statuses:
        if _STATUS_ORDER[status] > _STATUS_ORDER[result]:
            result = status
    return result


def _evaluate_delta(delta: MetricDelta, config: RegressionConfig) -> MetricRegression:
    """Map one metric delta to a PASS/WARNING/FAIL regression verdict."""
    thresholds = config.thresholds_for(delta.metric)
    if delta.verdict != MetricVerdict.REGRESSED or delta.delta is None:
        return MetricRegression(
            metric=delta.metric,
            baseline=delta.value_a,
            candidate=delta.value_b,
            delta=delta.delta,
            percent=delta.percent,
            direction=delta.direction,
            status=RegressionStatus.PASS,
            reason=f"{delta.metric}: no regression ({delta.verdict.value})",
        )
    magnitude = abs(delta.delta)
    pct = abs(delta.percent) if delta.percent is not None else None
    fail_hit = (
        thresholds.fail_abs is not None and magnitude >= thresholds.fail_abs
    ) or (thresholds.fail_pct is not None and pct is not None and pct >= thresholds.fail_pct)
    if fail_hit:
        return MetricRegression(
            metric=delta.metric,
            baseline=delta.value_a,
            candidate=delta.value_b,
            delta=delta.delta,
            percent=delta.percent,
            direction=delta.direction,
            status=RegressionStatus.FAIL,
            reason=f"{delta.metric}: regression exceeded failure threshold",
        )
    warn_hit = (
        thresholds.warn_abs is not None and magnitude >= thresholds.warn_abs
    ) or (thresholds.warn_pct is not None and pct is not None and pct >= thresholds.warn_pct)
    if warn_hit:
        return MetricRegression(
            metric=delta.metric,
            baseline=delta.value_a,
            candidate=delta.value_b,
            delta=delta.delta,
            percent=delta.percent,
            direction=delta.direction,
            status=RegressionStatus.WARNING,
            reason=f"{delta.metric}: regression exceeded warning threshold",
        )
    has_thresholds = (
        thresholds.warn_abs is not None
        or thresholds.fail_abs is not None
        or thresholds.warn_pct is not None
        or thresholds.fail_pct is not None
    )
    if has_thresholds:
        return MetricRegression(
            metric=delta.metric,
            baseline=delta.value_a,
            candidate=delta.value_b,
            delta=delta.delta,
            percent=delta.percent,
            direction=delta.direction,
            status=RegressionStatus.PASS,
            reason=f"{delta.metric}: sub-threshold regression tolerated",
        )
    return MetricRegression(
        metric=delta.metric,
        baseline=delta.value_a,
        candidate=delta.value_b,
        delta=delta.delta,
        percent=delta.percent,
        direction=delta.direction,
        status=RegressionStatus.WARNING,
        reason=f"{delta.metric}: regression with no configured threshold",
    )


def detect_from_comparison(
    comparison: RunComparison,
    config: RegressionConfig | None = None,
) -> RegressionReport:
    """Build a regression report from an existing comparison, read-only."""
    if not isinstance(comparison, RunComparison):
        raise TypeError(f"Expected RunComparison, got {type(comparison).__name__}")
    active = config if config is not None else RegressionConfig()
    warnings = list(comparison.warnings)
    metrics = [_evaluate_delta(delta, active) for delta in comparison.metrics]
    cases: list[CaseRegression] = []
    for case in comparison.cases:
        if not case.present_a or not case.present_b:
            if case.present_a and not case.present_b:
                cases.append(
                    CaseRegression(
                        case_id=case.case_id,
                        present_baseline=True,
                        present_candidate=False,
                        status=RegressionStatus.WARNING,
                        reason=f"Case {case.case_id!r} missing from candidate",
                    )
                )
            else:
                cases.append(
                    CaseRegression(
                        case_id=case.case_id,
                        present_baseline=False,
                        present_candidate=True,
                        status=RegressionStatus.PASS,
                        reason=f"Case {case.case_id!r} only in candidate",
                    )
                )
            continue
        evaluated = [_evaluate_delta(delta, active) for delta in case.metrics]
        status = _worst([entry.status for entry in evaluated])
        reason = f"Case {case.case_id!r}: {status.value}"
        if status != RegressionStatus.PASS:
            warnings.append(f"Case {case.case_id!r} regressed: {status.value}")
        cases.append(
            CaseRegression(
                case_id=case.case_id,
                present_baseline=True,
                present_candidate=True,
                status=status,
                metrics=evaluated,
                reason=reason,
            )
        )
    overall = _worst(
        [entry.status for entry in metrics] + [case.status for case in cases]
    )
    reasons = [
        f"{entry.metric}: {entry.status.value} ({entry.reason})"
        for entry in metrics
        if entry.status != RegressionStatus.PASS
    ]
    reasons += [
        f"{case.case_id}: {case.status.value} ({case.reason})"
        for case in cases
        if case.status != RegressionStatus.PASS
    ]
    if overall == RegressionStatus.PASS:
        reasons = ["No regression thresholds exceeded"]
    return RegressionReport(
        baseline_run_id=comparison.run_a_id,
        candidate_run_id=comparison.run_b_id,
        benchmark=comparison.benchmark,
        status=overall,
        metrics=metrics,
        cases=cases,
        missing_in_candidate=list(comparison.missing_in_b),
        missing_in_baseline=list(comparison.missing_in_a),
        warnings=warnings,
        reasons=reasons,
        detected_at=utcnow(),
    )


def detect_regressions(
    baseline: BenchmarkRun,
    candidate: BenchmarkRun,
    config: RegressionConfig | None = None,
    *,
    directions=None,
) -> RegressionReport:
    """Compare two runs and evaluate regressions without modifying inputs."""
    comparison = compare_runs(baseline, candidate, directions=directions)
    return detect_from_comparison(comparison, config)
