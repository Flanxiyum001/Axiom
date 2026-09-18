import uuid
from backend.orchestrator import Orchestrator
from backend.models.schemas import ResearchObjective, MetricDefinition, MetricDirection

def _make_objective():
    return ResearchObjective(
        title="Reduce Inference Latency",
        description="Reduce latency by at least 20% with <1% accuracy loss.",
        metrics=[
            MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE),
            MetricDefinition(name="accuracy", unit="ratio", direction=MetricDirection.MAXIMIZE),
            MetricDefinition(name="throughput", unit="ops", direction=MetricDirection.MAXIMIZE),
            MetricDefinition(name="gpu_memory_mb", unit="mb", direction=MetricDirection.MINIMIZE),
        ],
        constraints={"max_accuracy_degradation": 0.01},
        target={"latency_reduction": 0.20},
        max_experiments=5,
    )


def test_orchestrator_mock_loop_deterministic():
    """Run the full orchestrator loop in mock mode and verify deterministic behavior.

    The mock provider is offline and deterministic, so two runs with identical
    inputs must produce identical final analyses and objective achievement.
    """
    objective = _make_objective()
    baseline = {"latency_ms": 142.0, "accuracy": 0.914, "throughput": 70.0, "gpu_memory_mb": 5200.0}

    # First run
    orchestrator1 = Orchestrator(objective, baseline)
    result1 = orchestrator1.run_loop()

    # Second run (new orchestrator instance)
    orchestrator2 = Orchestrator(objective, baseline)
    result2 = orchestrator2.run_loop()

    # Both runs should achieve the objective (mock provider is designed to succeed on iteration 1)
    assert result1["objective_achieved"] is True
    assert result2["objective_achieved"] is True

    # The final analysis summary should be identical, confirming determinism
    # Compare summaries after stripping UUIDs (which are generated per run)
    import re
    def strip_uuids(text: str) -> str:
        return re.sub(r"[0-9a-fA-F-]{36}", "<UUID>", text)
    summary1 = strip_uuids(result1["final_analysis"].summary)
    summary2 = strip_uuids(result2["final_analysis"].summary)
    assert summary1 == summary2, "Final analysis summaries differ after normalizing UUIDs"


    # Ensure the orchestrator used the mock provider (no network calls)
    from backend.llm.mock import MockLLMProvider
    assert isinstance(orchestrator1.provider, MockLLMProvider)
    assert isinstance(orchestrator2.provider, MockLLMProvider)
