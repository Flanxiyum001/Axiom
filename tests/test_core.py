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
    # fp16_optimization is first in queue and should succeed
    orch.run_loop()
    
    results = orch.store.list_all_results()
    assert len(results) == 1 # Should stop after first success
    assert results[0].status == ExperimentStatus.COMPLETED

def test_orchestrator_max_experiments():
    obj = ResearchObjective(
        title="Optimize Latency",
        description="Reduce latency",
        metrics=[MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE)],
        constraints={},
        target={},
        max_experiments=0 # Stop immediately
    )
    baseline = {"latency_ms": 142.0}
    orch = Orchestrator(obj, baseline)
    orch.run_loop()
    
    results = orch.store.list_all_results()
    assert len(results) == 0
