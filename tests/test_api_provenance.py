"""API-level regression tests for workload and lever provenance."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from axiom.agents.analyst import AnalystAgent
from axiom.agents.planner import PlannerAgent
from axiom.agents.researcher import ResearcherAgent
from axiom.api.routes import ServiceState, build_router
from axiom.config import Settings
from axiom.domain.interfaces import ExperimentExecutor
from axiom.domain.models import ExperimentRun, Hypothesis, ResearchObjective, RunStatus
from axiom.execution.engine import ExperimentEngine
from axiom.providers.echo_provider import EchoReasoningProvider
from axiom.providers.schemas import CodeOutput


class FastEchoProvider(EchoReasoningProvider):
    """Fast deterministic provider for API tests; no external LLM or live calls."""

    def _code(self, context: dict[str, str]) -> CodeOutput:
        objective = ResearchObjective.model_validate_json(context["objective"])
        hypothesis = Hypothesis.model_validate_json(context["hypothesis"])
        lever = next(
            (name for name in ("batch_size", "threads", "precision") if name in hypothesis.statement),
            "batch_size",
        )
        code = (
            f'LEVER = "{lever}"\\n'
            "import json\\n"
            "import os\\n"
            'mode = os.environ.get("EXPERIMENT_MODE", "baseline")\\n'
            'value = 100.0 if mode == "baseline" else 75.0\\n'
            f'print(json.dumps({{"metrics": [{{"name": "{objective.metric}", "value": value, "unit": "ms", "iteration": 0}}]}}))\\n'
        )
        return CodeOutput(
            code=code,
            environment={},
            description=f"Fast synthetic API test for {lever}",
            parameters={},
        )


class AlwaysFailingExecutor(ExperimentExecutor):
    def execute(self, spec, timeout_seconds: float) -> ExperimentRun:
        return ExperimentRun(
            experiment_id=spec.id,
            status=RunStatus.FAILED,
            stderr="intentional test failure",
        )


def _build_test_client(tmp_path):
    settings = Settings(
        reasoning_provider="echo",
        executor_backend="local",
        db_path=":memory:",
        artifact_root=str(tmp_path),
        max_iterations=3,
        run_timeout_seconds=5.0,
    )
    state = ServiceState(settings)
    services = state.services()

    # Replace every reasoning role with a deterministic local provider so CI
    # never needs a Nebius credential and the tests remain fast.
    provider = FastEchoProvider()
    services.provider = provider
    services.researcher = ResearcherAgent(provider)
    services.planner = PlannerAgent(provider)
    services.analyst = AnalystAgent(provider)

    app = FastAPI()
    app.include_router(build_router(state))
    return TestClient(app), state, services


def _expected_lever(hypothesis: dict, plan: dict) -> str:
    text = hypothesis["statement"].lower()
    variable_names = " ".join(variable["name"].lower() for variable in plan["variables"])
    combined = f"{text} {variable_names}"
    for alias, canonical in (
        ("batch_size", "batch_size"),
        ("batch", "batch_size"),
        ("threads", "threads"),
        ("thread", "threads"),
        ("precision", "precision"),
    ):
        if alias in combined:
            return canonical
    return "batch_size"


def _assert_record_provenance(record: dict) -> None:
    assert record["spec"]["workload_type"] == "synthetic"
    expected = _expected_lever(record["hypothesis"], record["plan"])
    assert expected in record["spec"]["code"]
    assert record["plan"]["variables"]
    assert record["hypothesis"]["statement"]


def _create_objective(client: TestClient, description: str) -> str:
    response = client.post("/objectives", json={"description": description})
    assert response.status_code == 201, response.text
    return response.json()["objective"]["id"]


def test_run_response_and_history_keep_consistent_provenance(tmp_path):
    client, _, _ = _build_test_client(tmp_path)
    objective_id = _create_objective(client, "Reduce latency by 20%")

    response = client.post(
        f"/objectives/{objective_id}/run",
        json={"max_iterations": 1},
    )
    assert response.status_code == 200, response.text
    summary = response.json()["summary"]

    assert summary["target_met"] is True
    assert summary["workload_type"] == "synthetic"
    assert summary["lever"] == _expected_lever(summary["hypothesis"], summary["plan"])
    _assert_record_provenance(summary)

    history_response = client.get(f"/objectives/{objective_id}/history")
    assert history_response.status_code == 200, history_response.text
    history = history_response.json()
    assert len(history) == 1
    _assert_record_provenance(history[0])
    assert len(history[0]["runs"]) > 0


def test_max_iterations_response_keeps_provenance_for_latest_iteration(tmp_path):
    client, _, _ = _build_test_client(tmp_path)
    objective_id = _create_objective(client, "Reduce latency by 99%")

    response = client.post(
        f"/objectives/{objective_id}/run",
        json={"max_iterations": 3},
    )
    assert response.status_code == 200, response.text
    summary = response.json()["summary"]

    assert summary["target_met"] is False
    assert summary["stop_reason"] == "max_iterations"
    assert summary["iteration"] == 2
    assert summary["workload_type"] == "synthetic"
    assert summary["lever"] == "precision"
    _assert_record_provenance(summary)

    history = client.get(f"/objectives/{objective_id}/history").json()
    assert len(history) == 3
    for record in history:
        _assert_record_provenance(record)


def test_failed_execution_still_returns_provenance(tmp_path):
    client, _, services = _build_test_client(tmp_path)
    services.engine = ExperimentEngine(executor=AlwaysFailingExecutor())
    objective_id = _create_objective(client, "Reduce latency by 20%")

    response = client.post(
        f"/objectives/{objective_id}/run",
        json={"max_iterations": 1},
    )
    assert response.status_code == 200, response.text
    summary = response.json()["summary"]

    assert summary["target_met"] is False
    assert summary["evaluation"] is None
    assert summary["workload_type"] == "synthetic"
    assert summary["lever"] == _expected_lever(summary["hypothesis"], summary["plan"])
    _assert_record_provenance(summary)
