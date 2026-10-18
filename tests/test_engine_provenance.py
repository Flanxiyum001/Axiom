"""Workload provenance must survive baseline/candidate spec derivation."""

from axiom.domain.models import (
    Direction,
    ExperimentPlan,
    ExperimentRun,
    ExperimentSpec,
    MetricSample,
    PlanVariable,
    RunStatus,
)
from axiom.execution.engine import ExperimentEngine


class RecordingExecutor:
    def __init__(self) -> None:
        self.specs: list[ExperimentSpec] = []

    def execute(self, spec: ExperimentSpec, timeout_seconds: float) -> ExperimentRun:
        self.specs.append(spec)
        value = 100.0 if spec.environment["EXPERIMENT_MODE"] == "baseline" else 75.0
        return ExperimentRun(
            experiment_id=spec.id,
            status=RunStatus.COMPLETED,
            metrics=[MetricSample(name="latency_ms", value=value, unit="ms")],
        )


def test_engine_preserves_workload_type_for_baseline_and_candidate():
    executor = RecordingExecutor()
    engine = ExperimentEngine(executor=executor)
    plan = ExperimentPlan(
        hypothesis_id="hyp-test",
        variables=[
            PlanVariable(name="threads", baseline_value="1", candidate_value="4")
        ],
        metrics=["latency_ms"],
        repetitions=1,
    )
    candidate_spec = ExperimentSpec(
        plan_id=plan.id,
        name="thread-experiment",
        description="test provenance",
        code='print("safe")',
        workload_type="real_model_inference",
    )

    result = engine.run(plan, candidate_spec, timeout_seconds=5.0)

    assert result.baseline_spec.workload_type == "real_model_inference"
    assert result.candidate_spec.workload_type == "real_model_inference"
    assert [spec.environment["EXPERIMENT_MODE"] for spec in executor.specs] == [
        "baseline",
        "candidate",
    ]
    assert all(spec.workload_type == "real_model_inference" for spec in executor.specs)
