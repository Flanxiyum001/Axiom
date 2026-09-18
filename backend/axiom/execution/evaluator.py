"""Deterministic evaluation of experiment results.

This module is the constitutional core of AXIOM's integrity guarantee:
comparison of baseline vs candidate metrics is performed exclusively by this
deterministic code. No LLM ever decides whether an experiment succeeded.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict

from axiom.domain.interfaces import ExperimentEvaluator
from axiom.domain.models import (
    Direction,
    Evaluation,
    ExperimentPlan,
    ExperimentRun,
    ResearchObjective,
    RunStatus,
    StatisticalInfo,
)

logger = logging.getLogger("axiom.execution")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _stdev(values: list[float]) -> float:
    """Population standard deviation; 0.0 for single samples."""
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _welch_t(baseline: list[float], candidate: list[float]) -> tuple[float, float] | None:
    """Crude Welch t statistic and one-sided significance indicator.

    Returns (t_stat, approximate_one_sided_p) using a normal approximation,
    which is acceptable for MVP-scale repetition counts (>= 2 per side).
    """
    n1, n2 = len(baseline), len(candidate)
    if n1 < 2 or n2 < 2:
        return None
    m1, m2 = _mean(baseline), _mean(candidate)
    v1 = sum((x - m1) ** 2 for x in baseline) / (n1 - 1)
    v2 = sum((x - m2) ** 2 for x in candidate) / (n2 - 1)
    denom = math.sqrt(v1 / n1 + v2 / n2)
    if denom == 0:
        return None
    t = (m2 - m1) / denom
    # Normal approximation of the one-sided p-value.
    p_one_sided = 0.5 * math.erfc(t / math.sqrt(2))
    return t, p_one_sided


class DeterministicEvaluator(ExperimentEvaluator):
    """Pure-Python deterministic comparator; no network, no model calls."""

    def evaluate(
        self,
        *,
        baseline: ExperimentRun,
        candidate: ExperimentRun,
        plan: ExperimentPlan,
        objective: ResearchObjective,
    ) -> Evaluation:
        if baseline.status != RunStatus.COMPLETED or candidate.status != RunStatus.COMPLETED:
            raise ValueError(
                "Cannot evaluate non-completed runs: "
                f"baseline={baseline.status.value}, candidate={candidate.status.value}"
            )

        plan_metrics = list(plan.metrics) or sorted(
            {s.name for s in candidate.metrics}
        )
        base_groups: dict[str, list[float]] = defaultdict(list)
        cand_groups: dict[str, list[float]] = defaultdict(list)
        for sample in baseline.metrics:
            base_groups[sample.name].append(sample.value)
        for sample in candidate.metrics:
            cand_groups[sample.name].append(sample.value)

        baseline_means: dict[str, float] = {}
        candidate_means: dict[str, float] = {}
        deltas: dict[str, float] = {}
        statistics: list[StatisticalInfo] = []

        for metric in plan_metrics:
            base_vals = base_groups.get(metric, [])
            cand_vals = cand_groups.get(metric, [])
            if not base_vals or not cand_vals:
                logger.warning(
                    "Metric '%s' missing measurements (baseline=%d, candidate=%d); skipped",
                    metric,
                    len(base_vals),
                    len(cand_vals),
                )
                continue

            b_mean, c_mean = _mean(base_vals), _mean(cand_vals)
            baseline_means[metric] = b_mean
            candidate_means[metric] = c_mean
            # Delta: positive means the candidate value is higher.
            deltas[metric] = c_mean - b_mean

            base_sd, cand_sd = _stdev(base_vals), _stdev(cand_vals)
            statistics.append(
                StatisticalInfo(
                    metric=metric,
                    repetitions=len(cand_vals),
                    mean=c_mean,
                    stdev=cand_sd,
                    min=min(cand_vals),
                    max=max(cand_vals),
                    direction=objective.direction,
                )
            )

        # Improvement percent is only meaningful for the objective's metric.
        improvement_percent = None
        target = None
        target_met = False
        primary = objective.metric
        if primary in baseline_means and primary in candidate_means:
            b_mean = baseline_means[primary]
            c_mean = candidate_means[primary]
            # Minimize: lower candidate is better -> positive improvement.
            # Maximize: higher candidate is better -> positive improvement.
            sign = -1.0 if objective.direction == Direction.MINIMIZE else 1.0
            improvement_percent = (
                sign * (c_mean - b_mean) / abs(b_mean) * 100.0
                if b_mean != 0
                else sign * (c_mean - b_mean)
            )
            target = objective.target
            target_met = improvement_percent >= objective.target

        evaluation = Evaluation(
            run_id=candidate.id,
            baseline_run_id=baseline.id,
            baseline_metrics=baseline_means,
            candidate_metrics=candidate_means,
            deltas=deltas,
            improvement_percent=improvement_percent,
            target=target,
            target_met=target_met,
            statistics=statistics,
        )
        logger.info(
            "Evaluation %s: improvement=%.3f%% target=%.2f%% met=%s",
            evaluation.id,
            improvement_percent if improvement_percent is not None else float("nan"),
            objective.target,
            target_met,
        )
        return evaluation
