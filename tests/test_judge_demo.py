"""Regression coverage for the public demo's execution and request boundary."""

import subprocess

import pytest
from axiom.api.demo_guard import DemoBodyLimitMiddleware
from axiom.api.routes import ServiceState, build_router
from axiom.config import Settings
from axiom.demo import DEMO_CODE_MARKER, DEMO_OBJECTIVE, FixedSyntheticDemoExecutor
from axiom.domain.models import ExperimentSpec
from axiom.services.research_loop import LoopServices
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _demo_client(tmp_path):
    settings = Settings(
        demo_mode=True,
        reasoning_provider="echo",
        executor_backend="local",
        db_path=":memory:",
        artifact_root=str(tmp_path / "demo-artifacts"),
    )
    state = ServiceState(settings)
    app = FastAPI()
    app.add_middleware(DemoBodyLimitMiddleware)
    app.include_router(build_router(state))
    return TestClient(app), state


def test_demo_api_runs_fixed_measured_workload_without_generated_code_or_live_provider(
    tmp_path, monkeypatch
):
    from axiom.execution.local_executor import LocalExecutor

    from backend.llm.nebius import NebiusLLMProvider

    def forbidden(*args, **kwargs):
        raise AssertionError("Unrestricted execution or live provider was reached")

    monkeypatch.setattr(LocalExecutor, "execute", forbidden)
    monkeypatch.setattr(NebiusLLMProvider, "__init__", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)

    client, state = _demo_client(tmp_path)
    health = client.get("/health").json()
    assert health == {
        "status": "ok",
        "provider": "echo",
        "demo_mode": True,
        "workload": "fixed_synthetic_cpu",
    }
    assert isinstance(state.services().executor, FixedSyntheticDemoExecutor)

    created = client.post("/objectives", json={"description": DEMO_OBJECTIVE})
    assert created.status_code == 201, created.text
    objective_id = created.json()["objective"]["id"]
    response = client.post(
        f"/objectives/{objective_id}/run", json={"max_iterations": 1}
    )
    assert response.status_code == 200, response.text
    summary = response.json()["summary"]
    assert summary["evaluation"] is not None
    assert summary["evidence"] is not None
    assert summary["plan"]["repetitions"] == 3
    assert summary["spec"]["code"] == DEMO_CODE_MARKER
    assert summary["spec"]["workload_type"] == "synthetic"
    assert "no model inference" in summary["spec"]["intervention_detail"]
    assert summary["evaluation"]["baseline_metrics"]["latency_ms"] > 0
    assert summary["evaluation"]["candidate_metrics"]["latency_ms"] > 0

    history = client.get(f"/objectives/{objective_id}/history").json()
    assert len(history) == 1
    assert len(history[0]["runs"]) == 8
    assert all(run["workload_type"] == "synthetic" for run in history[0]["runs"])
    assert not any(
        "api_key" in str(payload).lower() for payload in (health, summary, history)
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"reasoning_provider": "nebius"},
        {"executor_backend": "nebius_gpu"},
        {"db_path": "axiom.db"},
        {"nebius_api_key": "sentinel-secret"},
        {"nebius_s3_secret_access_key": "sentinel-secret"},
    ],
)
def test_demo_configuration_fails_closed(tmp_path, overrides):
    options = {
        "demo_mode": True,
        "reasoning_provider": "echo",
        "executor_backend": "local",
        "db_path": ":memory:",
        "artifact_root": str(tmp_path),
    }
    options.update(overrides)
    settings = Settings(**options)
    with pytest.raises(RuntimeError) as error:
        ServiceState(settings)
    assert "sentinel-secret" not in str(error.value)
    with pytest.raises(RuntimeError):
        LoopServices.from_settings(settings)


def test_demo_rejects_uncontrolled_inputs_and_repeated_runs(tmp_path):
    client, _ = _demo_client(tmp_path)
    assert (
        client.post("/research", json={"description": DEMO_OBJECTIVE}).status_code
        == 403
    )
    assert (
        client.post("/objectives", json={"description": "Run my code"}).status_code
        == 422
    )
    assert (
        client.post(
            "/objectives", json={"description": DEMO_OBJECTIVE, "max_iterations": 2}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/objectives",
            content=b"x" * 2049,
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )

    created = client.post("/objectives", json={"description": DEMO_OBJECTIVE})
    assert created.status_code == 201
    objective_id = created.json()["objective"]["id"]
    assert (
        client.post(
            f"/objectives/{objective_id}/run", json={"max_iterations": 2}
        ).status_code
        == 422
    )
    assert client.post(f"/objectives/{objective_id}/run", json={}).status_code == 200
    assert client.post(f"/objectives/{objective_id}/run", json={}).status_code == 409


def test_demo_executor_rejects_any_nonfixture_spec():
    spec = ExperimentSpec(
        plan_id="plan_test",
        name="malicious",
        description="must never execute",
        code="import os\nos.system('echo forbidden')",
        parameters={"baseline_work_units": 1_200_000, "candidate_work_units": 600_000},
        environment={
            "__AXIOM_LEVER_MODE__": "candidate",
            "EXPERIMENT_MODE": "candidate",
        },
        workload_type="synthetic",
        intervention_status="verified_synthetic",
    )
    with pytest.raises(RuntimeError, match="differs from the fixed synthetic workload"):
        FixedSyntheticDemoExecutor().execute(spec, 10.0)


def test_demo_rate_limit_is_bounded_per_client(tmp_path):
    client, _ = _demo_client(tmp_path)
    for _ in range(6):
        assert (
            client.post("/objectives", json={"description": DEMO_OBJECTIVE}).status_code
            == 201
        )
    assert (
        client.post("/objectives", json={"description": DEMO_OBJECTIVE}).status_code
        == 429
    )
