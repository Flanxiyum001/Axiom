import pytest
from datetime import UTC, datetime
from axiom.domain.models import (
    Direction,
    ExperimentPlan,
    ExperimentRun,
    ExperimentSpec,
    MetricSample,
    ResearchObjective,
    RunStatus,
)
from axiom.execution.engine import ExperimentEngine
from axiom.execution.evaluator import DeterministicEvaluator
from axiom.domain.interfaces import ExperimentExecutor

class MockExecutor(ExperimentExecutor):
    def __init__(self):
        self.calls = []
        self.next_status = RunStatus.COMPLETED
        self.next_metrics = []

    def execute(self, spec, timeout_seconds):
        self.calls.append((spec, timeout_seconds))
        return ExperimentRun(
            experiment_id=spec.id,
            status=self.next_status,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            metrics=self.next_metrics,
            stdout=f"stdout for {spec.name}",
            stderr=f"stderr for {spec.name}",
        )

def test_engine_repetitions():
    executor = MockExecutor()
    engine = ExperimentEngine(executor)
    plan = ExperimentPlan(hypothesis_id="hyp_1", repetitions=3)
    spec = ExperimentSpec(plan_id=plan.id, name="test-candidate", description="test", code="print('test')")
    
    result = engine.run(plan, spec, 60.0)
    
    assert len(executor.calls) == 6
    baseline_calls = [c for c in executor.calls if c[0].environment.get("__AXIOM_LEVER_MODE__") == "baseline"]
    candidate_calls = [c for c in executor.calls if c[0].environment.get("__AXIOM_LEVER_MODE__") == "candidate"]
    assert len(baseline_calls) == 3
    assert len(candidate_calls) == 3
    assert all(c[1] == 60.0 for c in executor.calls)

def test_engine_baseline_candidate_pairing():
    executor = MockExecutor()
    engine = ExperimentEngine(executor)
    plan = ExperimentPlan(hypothesis_id="hyp_1", repetitions=1)
    spec = ExperimentSpec(
        plan_id=plan.id, 
        name="hyp_1-candidate", 
        description="desc", 
        code="code", 
        parameters={"p": 1},
        environment={"E": "V"}
    )
    
    result = engine.run(plan, spec, 60.0)
    
    assert result.baseline_spec.plan_id == spec.plan_id
    assert result.baseline_spec.description == spec.description
    assert result.baseline_spec.code == spec.code
    assert result.baseline_spec.parameters == spec.parameters
    assert result.baseline_spec.name == "hyp_1-baseline"
    assert result.baseline_spec.environment["__AXIOM_LEVER_MODE__"] == "baseline"
    assert result.baseline_spec.environment["E"] == "V"
    
    assert result.candidate_spec.name == "hyp_1-candidate"
    assert result.candidate_spec.environment["__AXIOM_LEVER_MODE__"] == "candidate"
    assert result.candidate_spec.environment["E"] == "V"


def test_engine_aggregates_metrics():
    class MetricExecutor(ExperimentExecutor):
        def __init__(self):
            self.count = 0
        def execute(self, spec, timeout_seconds):
            self.count += 1
            val = 100.0 if spec.environment["__AXIOM_LEVER_MODE__"] == "baseline" else 70.0
            val += self.count 
            return ExperimentRun(
                experiment_id=spec.id,
                status=RunStatus.COMPLETED,
                metrics=[MetricSample(name="latency_ms", value=val)],
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )

    engine = ExperimentEngine(MetricExecutor())
    plan = ExperimentPlan(hypothesis_id="hyp_1", repetitions=3)
    spec = ExperimentSpec(plan_id=plan.id, name="test", description="test", code="test")
    
    result = engine.run(plan, spec, 60.0)
    
    assert len(result.baseline_run.metrics) == 3
    assert len(result.candidate_run.metrics) == 3
    
    base_vals = [m.value for m in result.baseline_run.metrics]
    cand_vals = [m.value for m in result.candidate_run.metrics]
    assert all(v > 100.0 for v in base_vals)
    assert all(v > 70.0 for v in cand_vals)

def test_engine_failure_preserves_successful_samples():
    class MixedExecutor(ExperimentExecutor):
        def __init__(self):
            self.count = 0
        def execute(self, spec, timeout_seconds):
            self.count += 1
            if self.count == 2:
                return ExperimentRun(experiment_id=spec.id, status=RunStatus.FAILED, stderr="error")
            return ExperimentRun(
                experiment_id=spec.id,
                status=RunStatus.COMPLETED,
                metrics=[MetricSample(name="m", value=10.0)],
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )

    engine = ExperimentEngine(MixedExecutor())
    plan = ExperimentPlan(hypothesis_id="hyp_1", repetitions=3)
    spec = ExperimentSpec(plan_id=plan.id, name="test", description="test", code="test")
    
    result = engine.run(plan, spec, 60.0)
    
    assert result.baseline_run.status == RunStatus.FAILED
    assert len(result.baseline_run.metrics) == 2
    assert "--- Repetition 2 stderr ---\nerror" in result.baseline_run.stderr
    
    assert result.candidate_run.status == RunStatus.COMPLETED
    assert len(result.candidate_run.metrics) == 3

def test_engine_evaluator_compatibility():
    class FixedExecutor(ExperimentExecutor):
        def execute(self, spec, timeout_seconds):
            mode = spec.environment["__AXIOM_LEVER_MODE__"]
            if not hasattr(self, "count"): self.count = 0
            self.count += 1
            if mode == "baseline":
                vals = [100.0, 110.0, 90.0]
                v = vals[(self.count - 1) % 3]
            else:
                vals = [70.0, 75.0, 65.0]
                v = vals[(self.count - 4) % 3]
            return ExperimentRun(
                experiment_id=spec.id,
                status=RunStatus.COMPLETED,
                metrics=[MetricSample(name="latency_ms", value=v)],
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )

    engine = ExperimentEngine(FixedExecutor())
    plan = ExperimentPlan(hypothesis_id="hyp_1", repetitions=3, metrics=["latency_ms"])
    spec = ExperimentSpec(plan_id=plan.id, name="test", description="test", code="test")
    objective = ResearchObjective(
        description="Reduce latency", 
        metric="latency_ms", 
        direction=Direction.MINIMIZE, 
        target=20.0
    )
    
    result = engine.run(plan, spec, 60.0)
    evaluator = DeterministicEvaluator()
    evaluation = evaluator.evaluate(
        baseline=result.baseline_run,
        candidate=result.candidate_run,
        plan=plan,
        objective=objective
    )
    
    assert evaluation.baseline_metrics["latency_ms"] == 100.0
    assert evaluation.candidate_metrics["latency_ms"] == 70.0
    assert evaluation.improvement_percent == 30.0
    assert evaluation.target_met is True
    assert len(evaluation.statistics) == 1
    stats = evaluation.statistics[0]
    assert stats.repetitions == 3
    assert stats.mean == 70.0
    assert stats.min == 65.0
    assert stats.max == 75.0
    assert stats.stdev > 0

