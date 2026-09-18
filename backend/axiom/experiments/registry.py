"""Experiment registry.

Named, versioned experiment examples that AXIOM can reference. The MVP ships
a dependency-free synthetic CPU benchmark; real ML inference benchmarks
(torch, onnxruntime, vLLM) plug in here later without changing the loop.
"""

from __future__ import annotations

from dataclasses import dataclass

from axiom.providers.echo_provider import EchoReasoningProvider


@dataclass(frozen=True)
class ExperimentExample:
    """A registered, reusable experiment definition."""

    name: str
    description: str
    metric: str
    code: str
    baseline_env: dict[str, str]
    candidate_env: dict[str, str]


def _synthetic_benchmark() -> str:
    return EchoReasoningProvider.synthetic_benchmark_code(
        metric="latency_ms", lever="batch_size"
    )


SYNTHETIC_CPU_BENCHMARK = ExperimentExample(
    name="synthetic_cpu_benchmark",
    description=(
        "Self-contained CPU workload measuring latency in ms; candidate mode "
        "models a batched/optimized inference path."
    ),
    metric="latency_ms",
    code=_synthetic_benchmark(),
    baseline_env={"__AXIOM_LEVER_MODE__": "baseline"},
    candidate_env={"__AXIOM_LEVER_MODE__": "candidate"},
)


REGISTRY: dict[str, ExperimentExample] = {
    SYNTHETIC_CPU_BENCHMARK.name: SYNTHETIC_CPU_BENCHMARK,
}


def get_example(name: str) -> ExperimentExample:
    """Look up a registered experiment example by name."""
    if name not in REGISTRY:
        raise KeyError(f"Unknown experiment example '{name}'; known: {sorted(REGISTRY)}")
    return REGISTRY[name]
