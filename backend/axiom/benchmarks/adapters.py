"""Integration boundary: converts benchmark cases for the Experiment Runner."""

from __future__ import annotations

from axiom.benchmarks.models import BenchmarkCase
from axiom.experiments.runner import ExperimentRequest


def case_to_request(case: BenchmarkCase, system: str = "") -> ExperimentRequest:
    """Map case input and metadata onto runner input without provider coupling."""
    return ExperimentRequest(system=system, prompt=case.input, context=dict(case.metadata))
