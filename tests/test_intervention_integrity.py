"""A measured script must not silently become evidence for a different lever."""

import pytest

from axiom.agents.planner import PlannerAgent, _lever_from_statement
from axiom.domain.models import Hypothesis, ExperimentSpec
from axiom.providers.echo_provider import EchoReasoningProvider
from axiom.providers.schemas import CodeOutput
from axiom.services.objective_parser import parse_objective


@pytest.mark.parametrize("statement", ["Improve cache locality", "batch_size and threads", ""])
def test_ambiguous_or_missing_lever_is_unknown(statement):
    assert _lever_from_statement(statement) is None


def test_planner_preserves_conflicting_code_and_records_mismatch():
    class ConflictingProvider(EchoReasoningProvider):
        def _code(self, context):
            return CodeOutput(code='LEVER = "precision"\nprint("unrelated")',
                              environment={}, description="conflict", parameters={})
    objective = parse_objective("Reduce latency by 20%")
    hypothesis = Hypothesis(objective_id=objective.id, statement="Optimize threads", rationale="test")
    _, spec = PlannerAgent(ConflictingProvider()).design(hypothesis, objective)
    assert 'LEVER = "precision"' in spec.code
    assert spec.intervention_status == "mismatch"


def test_known_echo_implementation_identifies_actual_synthetic_treatment():
    provider = EchoReasoningProvider()
    objective = parse_objective("Reduce latency by 20%")
    hypothesis = provider._hypothesis({"objective": objective.model_dump_json()})
    _, spec = PlannerAgent(provider).design(hypothesis, objective)
    assert spec.intervention_status == "verified_synthetic"
    assert "arithmetic loop iterations" in spec.intervention_detail


def test_loop_does_not_support_unverified_generated_intervention(tmp_path):
    from tests.test_api_provenance import _build_test_client, _create_objective
    client, _, _ = _build_test_client(tmp_path)
    objective_id = _create_objective(client, "Reduce latency by 20%")
    response = client.post(f"/objectives/{objective_id}/run", json={"max_iterations": 1})
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["evaluation"]["target_met"] is True  # arithmetic comparison still honest
    assert summary["spec"]["intervention_status"] == "insufficient"
    assert summary["evidence"]["hypothesis_supported"] is False
    assert "Insufficient evidence" in summary["evidence"]["conclusion"]
    history = client.get(f"/objectives/{objective_id}/history").json()
    assert history[0]["spec"]["intervention_status"] == "insufficient"
    assert history[0]["evidence"] == summary["evidence"]


def test_local_executor_preserves_unicode_and_workload_in_manifest(tmp_path):
    import json
    from axiom.execution.local_executor import LocalExecutor
    from axiom.execution.artifacts import LocalArtifactStore
    spec = ExperimentSpec(plan_id="p", name="unicode", description="test",
                          code='print("\\u03bb")\nprint(\'{"metrics": [{"name": "latency_ms", "value": 1}]}\')',
                          workload_type="synthetic")
    run = LocalExecutor(artifact_store=LocalArtifactStore(str(tmp_path))).execute(spec, 5)
    assert "λ" in run.stdout
    assert run.metrics[0].value == 1
    assert run.workload_type == "synthetic"
    manifest = json.loads((tmp_path / run.id / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["workload_type"] == "synthetic"
