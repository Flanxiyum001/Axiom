import tempfile
import pytest

from axiom.config import Settings
from axiom.domain.models import (
    ExperimentSpec,
    ExperimentPlan,
    ExperimentRun,
    RunStatus,
)
from axiom.execution import ExperimentValidator
from axiom.execution.engine import ExperimentEngine
from axiom.services.research_loop import LoopServices, ResearchLoopConfig, ResearchLoopService
from axiom.services.objective_parser import parse_objective
from axiom.providers.echo_provider import EchoReasoningProvider
from axiom.agents.researcher import ResearcherAgent
from axiom.agents.planner import PlannerAgent
from axiom.agents.analyst import AnalystAgent

def create_valid_spec(name: str = "test-candidate") -> ExperimentSpec:
    return ExperimentSpec(
        plan_id="plan_1",
        name=name,
        description="desc",
        code="print('hello')",
        parameters={"p": 1},
        environment={"E": "V"},
    )

class CountingExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, spec, timeout_seconds):
        self.calls.append((spec, timeout_seconds))
        return ExperimentRun(
            experiment_id=spec.id,
            status=RunStatus.COMPLETED,
            metrics=[],
            stdout="",
            stderr="",
        )

def test_validator_accepts_valid_experiment_spec():
    validator = ExperimentValidator()
    spec = create_valid_spec()
    result = validator.validate(spec)
    assert result.valid
    assert result.reasons == []

def test_validator_rejects_empty_code():
    validator = ExperimentValidator()
    spec = create_valid_spec()
    spec.code = ""
    result = validator.validate(spec)
    assert not result.valid
    assert "code is empty" in result.reasons[0]

def test_validator_rejects_invalid_python():
    validator = ExperimentValidator()
    spec = create_valid_spec()
    spec.code = "def foo(:"
    result = validator.validate(spec)
    assert not result.valid
    assert "invalid Python source" in result.reasons[0]

def test_validator_rejects_os_system():
    validator = ExperimentValidator()
    spec = create_valid_spec()
    spec.code = "import os\nos.system('rm -rf /')"
    result = validator.validate(spec)
    assert not result.valid
    assert "os.system" in result.reasons[0]

def test_validator_rejects_subprocess_usage():
    validator = ExperimentValidator()
    spec = create_valid_spec()
    spec.code = "import subprocess\nsubprocess.run(['echo', 'hi'])"
    result = validator.validate(spec)
    assert not result.valid
    assert "subprocess.run" in result.reasons[0]

def test_validator_rejects_eval_and_exec():
    validator = ExperimentValidator()
    spec = create_valid_spec()
    spec.code = "eval('2+2')"
    result = validator.validate(spec)
    assert not result.valid
    assert "eval()" in result.reasons[0]

def test_invalid_spec_never_reaches_executor():
    validator = ExperimentValidator()
    executor = CountingExecutor()
    engine = ExperimentEngine(executor=executor, validator=validator)
    spec = create_valid_spec()
    spec.code = "import os\nos.system('echo')"
    result = engine.run(ExperimentPlan(hypothesis_id="h1", repetitions=1), spec, 60.0)
    assert len(executor.calls) == 0
    assert result.baseline_run.status == RunStatus.FAILED
    assert result.candidate_run.status == RunStatus.FAILED

def test_valid_spec_reaches_executor():
    validator = ExperimentValidator()
    executor = CountingExecutor()
    engine = ExperimentEngine(executor=executor, validator=validator)
    spec = create_valid_spec()
    result = engine.run(ExperimentPlan(hypothesis_id="h1", repetitions=1), spec, 60.0)
    assert len(executor.calls) == 2
    assert result.baseline_run.status == RunStatus.COMPLETED
    assert result.candidate_run.status == RunStatus.COMPLETED

def test_validation_failure_preserves_research_loop_resilience():
    settings = Settings(db_path=":memory:", artifact_root=tempfile.mkdtemp())
    services = LoopServices.from_settings(settings)
    objective = parse_objective("Reduce latency by 20%")
    objective.target = 99.0
    provider = EchoReasoningProvider()
    services = LoopServices(
        provider=provider,
        researcher=ResearcherAgent(provider),
        planner=PlannerAgent(provider),
        analyst=AnalystAgent(provider),
        executor=services.executor,
        evaluator=services.evaluator,
        repository=services.repository,
        artifact_store=services.artifact_store,
        engine=ExperimentEngine(executor=services.executor, validator=ExperimentValidator()),
    )
    service = ResearchLoopService(services, ResearchLoopConfig(max_iterations=2))
    original_design = services.planner.design
    def bad_design(hypothesis, objective, *, baseline_id=None):
        plan, spec = original_design(hypothesis, objective, baseline_id=baseline_id)
        spec.code = "import os\nos.system('echo')"
        return plan, spec
    services.planner.design = bad_design
    summary = service.run_objective(objective)
    assert summary.stopped is True
    assert summary.stop_reason == "max_iterations"
    history = services.repository.history_for_objective(objective.id)
    assert len(history) == 2
    for h in history:
        assert h.evidence is None
        assert h.runs[0].status == RunStatus.FAILED

def test_validation_failure_can_become_evidence():
    settings = Settings(db_path=":memory:", artifact_root=tempfile.mkdtemp())
    services = LoopServices.from_settings(settings)
    objective = parse_objective("Reduce latency by 20%")
    objective.target = 99.0
    provider = EchoReasoningProvider()
    services = LoopServices(
        provider=provider,
        researcher=ResearcherAgent(provider),
        planner=PlannerAgent(provider),
        analyst=AnalystAgent(provider),
        executor=services.executor,
        evaluator=services.evaluator,
        repository=services.repository,
        artifact_store=services.artifact_store,
        engine=ExperimentEngine(executor=services.executor, validator=ExperimentValidator()),
    )
    service = ResearchLoopService(services, ResearchLoopConfig(max_iterations=1))
    original_design = services.planner.design
    def bad_design(hypothesis, objective, *, baseline_id=None):
        plan, spec = original_design(hypothesis, objective, baseline_id=baseline_id)
        spec.code = "import os\nos.system('echo')"
        return plan, spec
    services.planner.design = bad_design
    summary = service.run_objective(objective)
    assert summary.evidence is None
    history = services.repository.history_for_objective(objective.id)
    assert len(history) == 1
    assert history[0].runs[0].status == RunStatus.FAILED
    assert history[0].evidence is None