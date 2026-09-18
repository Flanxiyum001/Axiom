import pytest
import uuid
from backend.models.schemas import (
    ResearchObjective, MetricDefinition, MetricDirection,
    ExperimentPlan, ExperimentStatus, Hypothesis, Analysis, ExperimentResult, Metric
)
from backend.experiments.runner import ExperimentRunner
from backend.experiments.evaluator import Evaluator
from backend.memory.store import ResearchMemoryStore
from backend.orchestrator import Orchestrator
from backend.llm.mock import MockLLMProvider
from backend.llm.base import LLMProvider
from backend.agents.researcher import ResearcherAgent
from backend.agents.planner import PlannerAgent
from backend.agents.analyst import AnalystAgent

def _make_objective():
    return ResearchObjective(
        title="Reduce Inference Latency",
        description="Reduce latency by at least 20% with <1% accuracy loss.",
        metrics=[
            MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE),
            MetricDefinition(name="accuracy", unit="ratio", direction=MetricDirection.MAXIMIZE),
        ],
        constraints={"max_accuracy_degradation": 0.01},
        target={"latency_reduction": 0.20},
        max_experiments=5,
    )

# 1 Schema validation
def test_schema_validation():
    obj = ResearchObjective(
        title="Test Obj", description="Desc",
        metrics=[MetricDefinition(name="latency", unit="ms", direction=MetricDirection.MINIMIZE)],
        constraints={}, target={}
    )
    assert isinstance(obj.id, uuid.UUID)
    assert obj.title == "Test Obj"

# 2 Experiment execution
def test_experiment_execution():
    runner = ExperimentRunner()
    plan = ExperimentPlan(
        hypothesis_id=uuid.uuid4(), title="baseline_benchmark", description="test",
        parameters={}, metrics=[], success_criteria="none"
    )
    result = runner.run(plan)
    assert result.status == ExperimentStatus.COMPLETED
    assert any(m.name == "latency_ms" for m in result.metrics)

# 3 Invalid experiment type
def test_invalid_experiment_type():
    runner = ExperimentRunner()
    plan = ExperimentPlan(
        hypothesis_id=uuid.uuid4(), title="invalid_type", description="test",
        parameters={}, metrics=[], success_criteria="none"
    )
    result = runner.run(plan)
    assert result.status == ExperimentStatus.FAILED
    assert result.error == "ExperimentNotFound"

# 4 Evaluator calculations
def test_evaluator_calculations():
    evaluator = Evaluator()
    result = ExperimentResult(
        experiment_id=uuid.uuid4(), status=ExperimentStatus.COMPLETED,
        metrics=[
            Metric(name="latency_ms", value=100.0, unit="ms", direction=MetricDirection.MINIMIZE),
            Metric(name="accuracy", value=0.91, unit="ratio", direction=MetricDirection.MAXIMIZE),
        ],
        duration=1.0, logs="test"
    )
    baseline = {"latency_ms": 142.0, "accuracy": 0.914}
    obj = ResearchObjective(
        title="T", description="T",
        metrics=[MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE)],
        constraints={}, target={}
    )
    ev = evaluator.evaluate(result, baseline, obj)
    assert ev["metrics_comparison"]["latency_ms"]["percent_change"] < -20
    assert ev["success"] is True

# 5 Memory storage
def test_memory_storage():
    store = ResearchMemoryStore()
    res = ExperimentResult(
        experiment_id=uuid.uuid4(), status=ExperimentStatus.COMPLETED,
        metrics=[], duration=0.5, logs="test"
    )
    store.save_result(res)
    assert len(store.list_all_results()) == 1
    assert store.get_result(res.experiment_id).logs == "test"

# 6 Metric directions from runner
def test_metric_directions_from_runner():
    runner = ExperimentRunner()
    plan = ExperimentPlan(
        hypothesis_id=uuid.uuid4(), title="fp16_optimization", description="test",
        parameters={}, metrics=[], success_criteria="none"
    )
    result = runner.run(plan)
    assert result.status == ExperimentStatus.COMPLETED
    m = {met.name: met for met in result.metrics}
    assert m["latency_ms"].direction == MetricDirection.MINIMIZE
    assert m["accuracy"].direction == MetricDirection.MAXIMIZE
    assert m["throughput"].direction == MetricDirection.MAXIMIZE
    assert m["gpu_memory_mb"].direction == MetricDirection.MINIMIZE

# 7 MockLLMProvider type check
def test_mock_provider_is_llm_provider():
    p = MockLLMProvider()
    assert isinstance(p, LLMProvider)
    assert p.name == "mock"

# 8 MockLLMProvider structured output
def test_mock_provider_returns_valid_structured_output():
    p = MockLLMProvider()
    h_ctx = {"objective": _make_objective().model_dump_json(), "iteration": "0", "prior_evidence": ""}
    hyp = p.generate(system="s", prompt="p", context=h_ctx, output_type=Hypothesis)
    assert isinstance(hyp, Hypothesis)
    assert hyp.title in ["Batch Size Tuning", "FP16 Precision Optimization"]
    pl_ctx = {"hypothesis": hyp.model_dump_json()}
    plan = p.generate(system="s", prompt="p", context=pl_ctx, output_type=ExperimentPlan)
    assert isinstance(plan, ExperimentPlan)
    assert plan.title in ["baseline_benchmark", "fp16_optimization", "batch_size_optimization"]
    a_ctx = {"experiment_result": ExperimentResult(
                experiment_id=uuid.uuid4(), status=ExperimentStatus.COMPLETED,
                metrics=[], duration=0.1, logs="test").model_dump_json(),
            "objective": h_ctx["objective"], "hypothesis": hyp.title}
    analysis = p.generate(system="s", prompt="p", context=a_ctx, output_type=Analysis)
    assert isinstance(analysis, Analysis)
    assert len(analysis.summary) > 0
