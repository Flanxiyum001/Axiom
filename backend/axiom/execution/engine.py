"""Experiment Engine: orchestrates baseline/candidate execution across N repetitions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from axiom.domain.interfaces import ExperimentExecutor
from axiom.domain.models import (
    Artifact,
    ExperimentPlan,
    ExperimentRun,
    ExperimentSpec,
    MetricSample,
    RunStatus,
)

logger = logging.getLogger("axiom.execution")


@dataclass
class ExperimentEngineResult:
    """Aggregated execution outcome for baseline and candidate conditions."""

    baseline_spec: ExperimentSpec
    candidate_spec: ExperimentSpec
    baseline_run: ExperimentRun
    candidate_run: ExperimentRun
    individual_runs: list[ExperimentRun] = field(default_factory=list)


class ExperimentEngine:
    """Orchestrates baseline/candidate execution across N repetitions."""

    def __init__(self, executor: ExperimentExecutor) -> None:
        self.executor = executor

    def run(
        self,
        plan: ExperimentPlan,
        spec_candidate: ExperimentSpec,
        timeout_seconds: float,
    ) -> ExperimentEngineResult:
        """Execute baseline and candidate specs for plan.repetitions each."""
        # 1. Derive candidate spec with __AXIOM_LEVER_MODE__ = "candidate"
        candidate_env = dict(spec_candidate.environment)
        candidate_env["__AXIOM_LEVER_MODE__"] = "candidate"
        cand_spec = spec_candidate.model_copy(update={"environment": candidate_env})

        # 2. Derive baseline spec with __AXIOM_LEVER_MODE__ = "baseline"
        base_name = spec_candidate.name
        if base_name.endswith("-candidate"):
            base_name = base_name[:-10]
        baseline_name = f"{base_name}-baseline"

        baseline_env = dict(spec_candidate.environment)
        baseline_env["__AXIOM_LEVER_MODE__"] = "baseline"

        base_spec = ExperimentSpec(
            plan_id=plan.id,
            name=baseline_name,
            description=spec_candidate.description,
            code=spec_candidate.code,
            parameters=dict(spec_candidate.parameters),
            environment=baseline_env,
        )

        repetitions = max(1, plan.repetitions)

        # 3. Execute baseline repetitions
        baseline_runs: list[ExperimentRun] = []
        for i in range(repetitions):
            logger.info(
                "Running baseline repetition %d/%d for plan %s (timeout=%.1fs)",
                i + 1,
                repetitions,
                plan.id,
                timeout_seconds,
            )
            run = self.executor.execute(base_spec, timeout_seconds)
            baseline_runs.append(run)

        # 4. Execute candidate repetitions
        candidate_runs: list[ExperimentRun] = []
        for i in range(repetitions):
            logger.info(
                "Running candidate repetition %d/%d for plan %s (timeout=%.1fs)",
                i + 1,
                repetitions,
                plan.id,
                timeout_seconds,
            )
            run = self.executor.execute(cand_spec, timeout_seconds)
            candidate_runs.append(run)

        # 5. Aggregate runs
        aggregated_baseline = self._aggregate_runs(base_spec.id, baseline_runs)
        aggregated_candidate = self._aggregate_runs(cand_spec.id, candidate_runs)

        return ExperimentEngineResult(
            baseline_spec=base_spec,
            candidate_spec=cand_spec,
            baseline_run=aggregated_baseline,
            candidate_run=aggregated_candidate,
            individual_runs=baseline_runs + candidate_runs,
        )

    def _aggregate_runs(self, spec_id: str, runs: list[ExperimentRun]) -> ExperimentRun:
        if not runs:
            return ExperimentRun(experiment_id=spec_id, status=RunStatus.FAILED)

        statuses = [r.status for r in runs]
        if any(s == RunStatus.TIMEOUT for s in statuses):
            overall_status = RunStatus.TIMEOUT
        elif any(s == RunStatus.FAILED for s in statuses):
            overall_status = RunStatus.FAILED
        elif all(s == RunStatus.COMPLETED for s in statuses):
            overall_status = RunStatus.COMPLETED
        else:
            overall_status = RunStatus.FAILED

        started_at = runs[0].started_at
        completed_at = runs[-1].completed_at

        exit_codes = [r.exit_code for r in runs if r.exit_code is not None]
        if overall_status == RunStatus.COMPLETED:
            exit_code = 0
        else:
            non_zero = [c for c in exit_codes if c != 0]
            exit_code = non_zero[0] if non_zero else (exit_codes[0] if exit_codes else None)

        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        metrics: list[MetricSample] = []
        artifacts: list[Artifact] = []

        for i, r in enumerate(runs, 1):
            if r.stdout:
                stdout_parts.append(f"--- Repetition {i} stdout ---\n{r.stdout}")
            if r.stderr:
                stderr_parts.append(f"--- Repetition {i} stderr ---\n{r.stderr}")
            metrics.extend(r.metrics)
            artifacts.extend(r.artifacts)

        stdout = "\n".join(stdout_parts)
        stderr = "\n".join(stderr_parts)

        return ExperimentRun(
            experiment_id=spec_id,
            status=overall_status,
            started_at=started_at,
            completed_at=completed_at,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            metrics=metrics,
            artifacts=artifacts,
        )
