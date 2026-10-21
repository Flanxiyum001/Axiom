"""Fixed, measured CPU demonstration with no experiment-code execution."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from axiom.agents.planner import PlannerAgent
from axiom.config import Settings
from axiom.domain.interfaces import ExperimentExecutor
from axiom.domain.models import (
    Artifact,
    ExpectedEffect,
    ExperimentRun,
    ExperimentSpec,
    Hypothesis,
    MetricSample,
    PlanVariable,
    ResearchObjective,
    RunStatus,
)
from axiom.execution.artifacts import ArtifactStore
from axiom.providers.echo_provider import EchoReasoningProvider
from axiom.providers.schemas import AnalysisOutput, CodeOutput, PlanOutput

DEMO_OBJECTIVE = "Reduce model inference latency by 20%"
DEMO_BASE_UNITS = 1_200_000
DEMO_CANDIDATE_UNITS = 600_000
DEMO_CODE_MARKER = "# Fixed synthetic CPU demo; this spec is never executed.\npass\n"
DEMO_INTERVENTION_DETAIL = (
    "Fixed in-process arithmetic workload: candidate performs fewer loop iterations "
    "than baseline. Timings measure this synthetic CPU task only; no model inference, "
    "batch-size change, quantization, multithreading, or GPU work is measured"
)


def validate_demo_configuration(settings: Settings) -> None:
    """Fail closed before constructing a live provider or unrestricted executor."""
    if settings.reasoning_provider != "echo" or settings.executor_backend != "local":
        raise RuntimeError(
            "Demo mode requires Echo reasoning and the fixed local demo executor"
        )
    if settings.db_path != ":memory:":
        raise RuntimeError(
            "Demo mode requires AXIOM_DB_PATH=:memory: to avoid exposing local history"
        )
    if (
        settings.nebius_api_key
        or settings.nebius_s3_access_key_id
        or settings.nebius_s3_secret_access_key
    ):
        raise RuntimeError("Demo mode must start without Nebius or storage credentials")


class DemoEchoReasoningProvider(EchoReasoningProvider):
    """Echo outputs for one fixed, clearly synthetic public demonstration."""

    def _hypothesis(self, context: dict[str, str]) -> Hypothesis:
        objective = ResearchObjective.model_validate_json(context["objective"])
        return Hypothesis(
            objective_id=objective.id,
            statement="Reducing fixed synthetic CPU work units should lower arithmetic-task latency",
            rationale="The candidate repeats the same arithmetic operation fewer times",
            expected_effect=ExpectedEffect(
                metric=objective.metric,
                direction=objective.direction,
                magnitude_percent=20.0,
                rationale="A prediction for this CPU fixture, not a model-inference claim",
            ),
            iteration=int(context.get("iteration", "0")),
        )

    def _plan(self, context: dict[str, str]) -> PlanOutput:
        objective = ResearchObjective.model_validate_json(context["objective"])
        return PlanOutput(
            variables=[
                PlanVariable(
                    name="synthetic_cpu_work_units",
                    baseline_value=f"{DEMO_BASE_UNITS} arithmetic iterations",
                    candidate_value=f"{DEMO_CANDIDATE_UNITS} arithmetic iterations",
                )
            ],
            metrics=[objective.metric],
            repetitions=3,
            timeout_seconds=10.0,
        )

    def _code(self, context: dict[str, str]) -> CodeOutput:
        return CodeOutput(
            code=DEMO_CODE_MARKER,
            description="Fixed synthetic CPU arithmetic; spec code is never executed",
            environment={},
            parameters={
                "baseline_work_units": DEMO_BASE_UNITS,
                "candidate_work_units": DEMO_CANDIDATE_UNITS,
            },
        )

    def _analysis(self, context: dict[str, str]) -> AnalysisOutput:
        evaluation = json.loads(context["evaluation"])
        improvement = evaluation.get("improvement_percent")
        met = bool(evaluation.get("target_met", False))
        return AnalysisOutput(
            hypothesis_supported=met,
            confidence=0.5,
            observations=[
                (
                    f"Observed synthetic CPU task improvement: {improvement}%"
                    if improvement is not None
                    else "Synthetic CPU task improvement was not computed"
                )
            ],
            limitations=[
                "One local synthetic CPU workload; timing depends on host load"
            ],
            conclusion=(
                "The fixed synthetic CPU task met its measured target in this run"
                if met
                else "The fixed synthetic CPU task did not meet its measured target in this run"
            ),
        )


class DemoPlanner(PlannerAgent):
    def design(self, hypothesis, objective, *, baseline_id=None):
        if objective.description != DEMO_OBJECTIVE or objective.metric != "latency_ms":
            raise RuntimeError("Demo objective differs from the fixed fixture")
        plan, spec = super().design(hypothesis, objective, baseline_id=baseline_id)
        if (
            plan.variables
            != [
                PlanVariable(
                    name="synthetic_cpu_work_units",
                    baseline_value=f"{DEMO_BASE_UNITS} arithmetic iterations",
                    candidate_value=f"{DEMO_CANDIDATE_UNITS} arithmetic iterations",
                )
            ]
            or plan.metrics != ["latency_ms"]
            or plan.repetitions != 3
            or plan.timeout_seconds != 10.0
            or spec.code != DEMO_CODE_MARKER
            or spec.parameters
            != {
                "baseline_work_units": DEMO_BASE_UNITS,
                "candidate_work_units": DEMO_CANDIDATE_UNITS,
            }
        ):
            raise RuntimeError("Demo plan differs from the fixed synthetic fixture")
        spec.intervention_status = "verified_synthetic"
        spec.intervention_detail = DEMO_INTERVENTION_DETAIL
        return plan, spec


class FixedSyntheticDemoExecutor(ExperimentExecutor):
    """Measure a compiled-in arithmetic loop; never reads or executes spec.code."""

    def execute(self, spec: ExperimentSpec, timeout_seconds: float) -> ExperimentRun:
        if (
            spec.code != DEMO_CODE_MARKER
            or spec.workload_type != "synthetic"
            or spec.parameters
            != {
                "baseline_work_units": DEMO_BASE_UNITS,
                "candidate_work_units": DEMO_CANDIDATE_UNITS,
            }
            or spec.intervention_status != "verified_synthetic"
        ):
            raise RuntimeError("Demo spec differs from the fixed synthetic workload")
        mode = spec.environment.get("__AXIOM_LEVER_MODE__")
        if (
            mode not in {"baseline", "candidate"}
            or spec.environment.get("EXPERIMENT_MODE") != mode
            or set(spec.environment) != {"__AXIOM_LEVER_MODE__", "EXPERIMENT_MODE"}
        ):
            raise RuntimeError("Demo run mode is invalid")
        units = DEMO_BASE_UNITS if mode == "baseline" else DEMO_CANDIDATE_UNITS
        started_at = datetime.now(UTC)
        start = time.perf_counter()
        deadline = start + min(max(timeout_seconds, 0.001), 10.0)
        checksum = 0
        timed_out = False
        for index in range(units):
            checksum = (checksum * 31 + 1) % 1_000_003
            if index % 10_000 == 0 and time.perf_counter() > deadline:
                timed_out = True
                break
        performed = index + 1
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        status = (
            RunStatus.TIMEOUT
            if timed_out or time.perf_counter() > deadline
            else RunStatus.COMPLETED
        )
        return ExperimentRun(
            experiment_id=spec.id,
            workload_type="synthetic",
            status=status,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            exit_code=0 if status == RunStatus.COMPLETED else None,
            stdout=f"Fixed synthetic CPU arithmetic: {mode}, {performed} iterations, checksum {checksum}",
            metrics=(
                [MetricSample(name="latency_ms", value=elapsed_ms, unit="ms")]
                if status == RunStatus.COMPLETED
                else []
            ),
        )


class DemoNoArtifactStore(ArtifactStore):
    """Fail closed if a future demo path tries to write or read host artifacts."""

    def save_output(self, run_id: str, name: str, content: bytes) -> Artifact:
        raise RuntimeError("Artifact access is disabled in demo mode")

    def copy_into_run(self, run_id: str, source: Path) -> Artifact:
        raise RuntimeError("Artifact access is disabled in demo mode")

    def read(self, artifact: Artifact) -> bytes:
        raise RuntimeError("Artifact access is disabled in demo mode")
