
# Real‑model demo (optional)
# This demo shows the full reasoning flow with the Nebius provider.
# It re‑uses the existing deterministic demo structure but swaps the LLM provider.
# The experiment execution remains deterministic (mock) – only the LLM calls are real.

import os
import sys
from pathlib import Path

from backend.orchestrator import Orchestrator
from backend.models.schemas import ResearchObjective, MetricDefinition, MetricDirection

def _check_env():
    required = ["NEBIUS_API_KEY", "NEBIUS_BASE_URL", "NEBIUS_MODEL"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print("Nebius demo not configured – missing environment variables:")
        for v in missing:
            print(f"  - {v}")
        print("Set them in .env or export before running this demo.")
        return False
    return True

def main():
    if not _check_env():
        return 0

    # Switch provider via config – set env var for this process only
    os.environ["AXIOM_LLM_PROVIDER"] = "nebius"

    # Define a simple objective (same as local demo)
    objective = ResearchObjective(
        title="Reduce Inference Latency",
        description="Reduce inference latency by at least 20% while keeping accuracy degradation below 1%.",
        metrics=[
            MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE),
            MetricDefinition(name="accuracy", unit="ratio", direction=MetricDirection.MAXIMIZE),
        ],
        constraints={"max_accuracy_degradation": 0.01},
        target={"latency_reduction": 0.20},
        max_experiments=3,
    )
    baseline = {"accuracy": 0.914, "latency_ms": 142.0}

    orchestrator = Orchestrator(objective, baseline)
    result = orchestrator.run_loop()
    print("\nDemo completed. Summary:")
    print(result)
    return 0

if __name__ == "__main__":
    sys.exit(main())
