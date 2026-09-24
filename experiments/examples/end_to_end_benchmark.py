#!/usr/bin/env python
"""End-to-end Experiment Layer demo.

Loads the bundled benchmark dataset, runs every case through the Experiment
Runner with a deterministic mock provider, evaluates each result, aggregates
everything into a benchmark report, and prints it.

Run from the repository root with no credentials:

    PYTHONPATH=backend python experiments/examples/end_to_end_benchmark.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../backend")))

from pydantic import BaseModel

from axiom.benchmarks.loader import load_example
from axiom.domain.interfaces import ReasoningProvider
from axiom.evaluation.evaluators import LatencyEvaluator, ResponseEvaluator
from axiom.evaluation.framework import EvaluationFramework
from axiom.experiments.runner import ExperimentRunner
from axiom.pipeline.pipeline import ExperimentPipeline
from axiom.reporting.aggregation import format_text


class TextAnswer(BaseModel):
    """Simple text output standing in for any provider response schema."""

    answer: str


class EchoProvider(ReasoningProvider):
    """Deterministic mock provider answering from the case prompt."""

    name = "echo"

    def generate(self, *, system, prompt, context, output_type):
        return TextAnswer(answer=f"Response to: {prompt}")


def main() -> int:
    """Run the full dataset → runner → evaluation → report flow."""
    dataset = load_example()
    print(f"Loaded benchmark {dataset.name!r} with {len(dataset.cases)} cases.")

    pipeline = ExperimentPipeline(
        ExperimentRunner(EchoProvider()),
        EvaluationFramework([LatencyEvaluator(5000.0), ResponseEvaluator()]),
    )
    outcome = pipeline.run(dataset, output_type=TextAnswer, label="demo")

    for record in outcome.records:
        print(f"{record.case_id}: experiment={record.experiment.status.value}")
    for failure in outcome.failures:
        print(f"{failure.case_id}: FAILED at {failure.stage}: {failure.error}")

    if outcome.report is None:
        print("No records produced; no report generated.")
        return 1
    print()
    print(format_text(outcome.report))
    if outcome.failures or any(
        record.experiment.status.value != "completed" for record in outcome.records
    ):
        print("Note: not all cases completed successfully; see details above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
