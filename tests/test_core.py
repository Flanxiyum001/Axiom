import pytest
import uuid
from backend.models.schemas import (
    ResearchObjective, MetricDefinition, MetricDirection,
    ExperimentPlan, ExperimentStatus, Hypothesis
)
from backend.experiments.runner import ExperimentRunner
from backend.experiments.evaluator import Evaluator
from backend.memory.store import ExperimentStore
from backend.orchestrator import Orchestrator


def test_schema_validation():
    obj = ResearchObjective(
        title="Test Objective",
        description="Test Description",
        metrics=[MetricDefinition(name="latency", unit="ms", direction=MetricDirection.MINIMIZE)],
        constraints={},
        target={}
    )
    assert isinstance(obj.id, uuid.UUID)
    assert obj.title == "Test Objective"


def test_experiment_execution():
    runner = ExperimentRunner()
    plan = ExperimentPlan(
        hypothesis_id=uuid.uuid4(),
        title="baseline_benchmark",
        description="test",
        parameters={},
        metrics=[],
        success_criteria="none"
    )
    result = runner.run(plan)
    assert result.status == ExperimentStatus.COMPLETED
    assert len(result.metrics) > 0
    assert any(m.name == "latency_ms" for m in result.metrics)


def test_invalid_experiment_type():
    runner = ExperimentRunner()
    plan = ExperimentPlan(
        hypothesis_id=uuid.uuid4(),
        title="invalid_type",
        description="test",
        parameters={},
        metrics=[],
        success_criteria="none"
    )
    result = runner.run(plan)
    assert result.status == ExperimentStatus.FAILED
    assert result.error == "ExperimentNotFound"
def test_evaluator_calculations():
    evaluator = Evaluator()
    from backend.models.schemas import ExperimentResult, Metric

    result = ExperimentResult(
        experiment_id=uuid.uuid4(),
        status=ExperimentStatus.COMPLETED,
        metrics=[
            Metric(name="latency_ms", value=100.0, unit="ms", direction=MetricDirection.MINIMIZE),
            Metric(name="accuracy", value=0.91, unit="ratio", direction=MetricDirection.MAXIMIZE)
        ],
        duration=1.0,
        logs="test"
    )

    baseline = {"latency_ms": 142.0, "accuracy": 0.914}
    obj = ResearchObjective(
        title="Test", description="Test",
        metrics=[MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE)],
        constraints={}, target={}
    )

    evaluation = evaluator.evaluate(result, baseline, obj)

    assert evaluation["metrics_comparison"]["latency_ms"]["percent_change"] < -20
    assert evaluation["success"] is True


def test_memory_storage():
    store = ExperimentStore()
    from backend.models.schemas import ExperimentResult
    res = ExperimentResult(
        experiment_id=uuid.uuid4(),
        status=ExperimentStatus.COMPLETED,
        metrics=[],
        duration=0.5,
        logs="test"
    )
    store.save_result(res)
    assert len(store.list_all_results()) == 1
    assert store.get_result(res.experiment_id).logs == "test"
def test_metric_directions_from_runner():
    """Test that the runner returns metrics with correct directions."""
    runner = ExperimentRunner()
    plan = ExperimentPlan(
        hypothesis_id=uuid.uuid4(),
        title="fp16_optimization",
        description="test",
        parameters={},
        metrics=[],
        success_criteria="none"
    )
    result = runner.run(plan)
    assert result.status == ExperimentStatus.COMPLETED

    metric_map = {m.name: m for m in result.metrics}

    assert metric_map["latency_ms"].direction == MetricDirection.MINIMIZE
    assert metric_map["accuracy"].direction == MetricDirection.MAXIMIZE
    assert metric_map["throughput"].direction == MetricDirection.MAXIMIZE
    assert metric_map["gpu_memory_mb"].direction == MetricDirection.MINIMIZE


def test_evaluator_with_runner_result():
    """Test the evaluator with actual runner output (not manually created metrics)."""
    runner = ExperimentRunner()
    plan = ExperimentPlan(
        hypothesis_id=uuid.uuid4(),
        title="fp16_optimization",
        description="test",
        parameters={},
        metrics=[],
        success_criteria="none"
    )
    result = runner.run(plan)
    assert result.status == ExperimentStatus.COMPLETED

    baseline = {
        "accuracy": 0.914,
        "latency_ms": 142.0,
        "throughput": 70.0,
        "gpu_memory_mb": 5200.0
    }
    obj = ResearchObjective(
        title="Test",
        description="Test",
        metrics=[
            MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE),
            MetricDefinition(name="accuracy", unit="ratio", direction=MetricDirection.MAXIMIZE),
        ],
        constraints={"max_accuracy_degradation": 0.01},
        target={"latency_reduction": 0.20}
    )

    evaluator = Evaluator()
    evaluation = evaluator.evaluate(result, baseline, obj)

    latency_comp = evaluation["metrics_comparison"]["latency_ms"]
    assert latency_comp["percent_change"] < -20

    accuracy_comp = evaluation["metrics_comparison"]["accuracy"]
    accuracy_degradation = accuracy_comp["baseline"] - accuracy_comp["experiment"]
    assert accuracy_degradation <= 0.01

    assert evaluation["success"] is True
    assert evaluation["overall_constraint_satisfied"] is True


def test_fp16_satisfies_objective():
    """Regression test: FP16 experiment should satisfy the current MVP objective."""
    runner = ExperimentRunner()
    plan = ExperimentPlan(
        hypothesis_id=uuid.uuid4(),
        title="fp16_optimization",
        description="test",
        parameters={},
        metrics=[],
        success_criteria="none"
    )
    result = runner.run(plan)
    assert result.status == ExperimentStatus.COMPLETED

    baseline = {
        "accuracy": 0.914,
        "latency_ms": 142.0,
        "throughput": 70.0,
        "gpu_memory_mb": 5200.0
    }
    obj = ResearchObjective(
        title="Reduce Inference Latency",
        description="Reduce inference latency by at least 20% while keeping accuracy degradation below 1%.",
        metrics=[
            MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE),
            MetricDefinition(name="accuracy", unit="ratio", direction=MetricDirection.MAXIMIZE)
        ],
        constraints={"max_accuracy_degradation": 0.01},
        target={"latency_reduction": 0.20},
        max_experiments=5
    )

    evaluator = Evaluator()
    evaluation = evaluator.evaluate(result, baseline, obj)

    assert evaluation["success"] is True, f"FP16 should satisfy objective, got: {evaluation}"
    assert evaluation["overall_constraint_satisfied"] is True

    latency_comp = evaluation["metrics_comparison"]["latency_ms"]
    assert latency_comp["baseline"] == 142.0
    assert latency_comp["experiment"] == 85.0
    assert abs(latency_comp["percent_change"] - (-40.14)) < 0.1

    accuracy_comp = evaluation["metrics_comparison"]["accuracy"]
    assert accuracy_comp["baseline"] == 0.914
    assert accuracy_comp["experiment"] == 0.910


def test_orchestrator_stopping_on_success():
    obj = ResearchObjective(
        title="Optimize Latency",
        description="Reduce latency",
        metrics=[MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE)],
        constraints={},
        target={},
        max_experiments=5
    )
    baseline = {"latency_ms": 142.0}
    orch = Orchestrator(obj, baseline)
    orch.run_loop()

    results = orch.store.list_all_results()
    assert len(results) == 1
    assert results[0].status == ExperimentStatus.COMPLETED


def test_orchestrator_max_experiments():
    obj = ResearchObjective(
        title="Optimize Latency",
        description="Reduce latency",
        metrics=[MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE)],
        constraints={},
        target={},
        max_experiments=0
    )
    baseline = {"latency_ms": 142.0}
    orch = Orchestrator(obj, baseline)
    orch.run_loop()

    results = orch.store.list_all_results()
    assert len(results) == 0
