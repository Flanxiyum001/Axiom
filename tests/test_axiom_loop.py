import tempfile

import pytest

from axiom.config import Settings
from axiom.domain.models import Direction, Hypothesis
from axiom.experiments.registry import get_example
from axiom.memory.sqlite_repo import SqliteRepository
from axiom.providers.echo_provider import EchoReasoningProvider
from axiom.providers.schemas import AnalysisOutput, CodeOutput, PlanOutput
from axiom.domain.models import Hypothesis as HypothesisModel
from axiom.services.objective_parser import ObjectiveParseError, parse_objective
from axiom.services.research_loop import LoopServices, ResearchLoopConfig, ResearchLoopService
from axiom.agents.planner import PlannerAgent


def test_parse_latency_objective():
    objective = parse_objective("Reduce model inference latency by 20%")
    assert objective.metric == "latency_ms"
    assert objective.direction == Direction.MINIMIZE
    assert objective.target == 20.0


def test_parse_throughput_objective():
    objective = parse_objective("Increase throughput by 15%")
    assert objective.metric == "throughput"
    assert objective.direction == Direction.MAXIMIZE
    assert objective.target == 15.0


def test_parse_rejects_short_description():
    with pytest.raises(ObjectiveParseError):
        parse_objective("ab")


def test_echo_provider_plan_includes_objective_metric():
    provider = EchoReasoningProvider()
    objective = parse_objective("Reduce latency by 20%")
    hypothesis = provider.generate(
        system="test",
        prompt="test",
        context={"objective": objective.model_dump_json(), "iteration": "0"},
        output_type=HypothesisModel,
    )
    assert hypothesis.objective_id == objective.id
    assert "batch_size" in hypothesis.statement
    plan = provider.generate(
        system="test",
        prompt="test",
        context={"objective": objective.model_dump_json(), "hypothesis": hypothesis.model_dump_json()},
        output_type=PlanOutput,
    )
    assert objective.metric in plan.metrics
    assert plan.repetitions == 3
    code = provider.generate(
        system="test",
        prompt="test",
        context={"objective": objective.model_dump_json(), "hypothesis": hypothesis.model_dump_json()},
        output_type=CodeOutput,
    )
    assert "LEVER" in code.code
    assert "metrics" in code.code


def test_registry_example():
    example = get_example("synthetic_cpu_benchmark")
    assert example.metric == "latency_ms"
    assert example.baseline_env["__AXIOM_LEVER_MODE__"] == "baseline"
    assert example.candidate_env["__AXIOM_LEVER_MODE__"] == "candidate"


def test_planner_design_sets_candidate_mode():
    provider = EchoReasoningProvider()
    planner = PlannerAgent(provider)
    objective = parse_objective("Reduce latency by 20%")
    hypothesis = Hypothesis(objective_id=objective.id, statement="Optimizing batch_size helps", rationale="test")
    plan, spec = planner.design(hypothesis, objective)
    assert objective.metric in plan.metrics
    assert spec.environment["__AXIOM_LEVER_MODE__"] == "candidate"
    assert spec.plan_id == plan.id


def test_research_loop_reaches_target():
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(db_path=":memory:", artifact_root=tmp)
        services = LoopServices.from_settings(settings)
        objective = parse_objective("Reduce model inference latency by 20%")
        service = ResearchLoopService(services, ResearchLoopConfig(max_iterations=2))
        summary = service.run_objective(objective)
        assert summary.target_met is True
        assert summary.evaluation is not None
        assert summary.evaluation.improvement_percent >= objective.target
        assert summary.evidence is not None
        assert summary.evidence.hypothesis_supported is True
        history = services.repository.history_for_objective(objective.id)
        assert len(history) == 1
        assert len(history[0].runs) == 2


def test_repository_roundtrip():
    repository = SqliteRepository(db_path=":memory:")
    objective = parse_objective("Reduce latency by 20%")
    repository.save_objective(objective)
    assert repository.get_objective(objective.id) is not None
    assert repository.next_hypothesis_number(objective.id) == 0
    hypothesis = Hypothesis(objective_id=objective.id, statement="test", rationale="test", iteration=0)
    repository.save_hypothesis(hypothesis)
    assert repository.next_hypothesis_number(objective.id) == 1
    assert len(repository.list_hypotheses(objective.id)) == 1


def test_parse_metrics_rejects_nonfinite():
    from axiom.execution.metrics_protocol import parse_metrics
    assert parse_metrics('{"metrics": [{"name": "m", "value": NaN}]}') == []
    assert parse_metrics('{"metrics": [{"name": "m", "value": Infinity}]}') == []
    assert parse_metrics('{"metrics": [{"name": "m", "value": -Infinity}]}') == []
    assert len(parse_metrics('{"metrics": [{"name": "m", "value": 1.5}]}')) == 1


def test_artifact_store_rejects_traversal():
    from axiom.execution.artifacts import ArtifactStore
    with tempfile.TemporaryDirectory() as tmp:
        store = ArtifactStore(root=tmp)
        for bad in ["../../evil.txt", "a/b.txt", "a\\b.txt", "", ".", ".."]:
            with pytest.raises(ValueError):
                store.save_output("run1", bad, b"x")


def test_loop_failed_runs_continue():
    from axiom.providers.echo_provider import EchoReasoningProvider
    from axiom.providers.schemas import CodeOutput
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(db_path=":memory:", artifact_root=tmp)
        services = LoopServices.from_settings(settings)
        original = EchoReasoningProvider._code
        EchoReasoningProvider._code = lambda self, ctx: CodeOutput(code="raise RuntimeError('broken')", environment={}, description="broken", parameters={})
        try:
            objective = parse_objective("Reduce latency by 20%")
            service = ResearchLoopService(services, ResearchLoopConfig(max_iterations=2))
            summary = service.run_objective(objective)
            assert summary.target_met is False
            assert summary.evaluation is None
            assert summary.evidence is None
            assert len(services.repository.history_for_objective(objective.id)) == 2
        finally:
            EchoReasoningProvider._code = original
