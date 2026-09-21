"""Experiment pipeline: dataset cases through runner, evaluation, aggregation."""

from __future__ import annotations

from axiom.benchmarks.adapters import case_to_request
from axiom.benchmarks.models import BenchmarkDataset
from axiom.domain.interfaces import T
from axiom.evaluation.framework import EvaluationFramework
from axiom.experiments.runner import ExperimentRunner
from axiom.pipeline.models import CaseFailure, PipelineResult
from axiom.reporting.aggregation import aggregate_benchmark
from axiom.reporting.models import CaseRecord


class ExperimentPipeline:
    """Lightweight orchestration over runner, framework, and aggregation."""

    def __init__(
        self,
        runner: ExperimentRunner,
        framework: EvaluationFramework,
        *,
        fail_fast: bool = False,
    ) -> None:
        """Bind existing components; fail_fast re-raises instead of recording."""
        self.runner = runner
        self.framework = framework
        self.fail_fast = fail_fast

    def run(
        self,
        dataset: BenchmarkDataset,
        *,
        output_type: type[T],
        system: str = "",
        label: str = "",
    ) -> PipelineResult:
        """Execute every case, evaluate, and aggregate successes into a report."""
        if not isinstance(dataset, BenchmarkDataset):
            raise TypeError(f"Expected BenchmarkDataset, got {type(dataset).__name__}")
        records: list[CaseRecord] = []
        failures: list[CaseFailure] = []
        for case in dataset.cases:
            try:
                experiment = self.runner.run(case_to_request(case, system), output_type=output_type)
            except Exception as exc:
                self._handle(failures, case.id, "run", exc)
                continue
            try:
                evaluation = self.framework.evaluate(experiment)
                records.append(CaseRecord(case_id=case.id, experiment=experiment, evaluation=evaluation))
            except Exception as exc:
                self._handle(failures, case.id, "evaluate", exc)
        report = None
        if records:
            report = aggregate_benchmark(dataset.name, records, label=label)
        return PipelineResult(
            benchmark=dataset.name,
            label=label,
            report=report,
            records=records,
            failures=failures,
        )

    def _handle(self, failures: list[CaseFailure], case_id: str, stage: str, exc: Exception) -> None:
        """Record a case failure, or re-raise when fail_fast is configured."""
        if self.fail_fast:
            raise exc
        failures.append(CaseFailure(case_id=case_id, stage=stage, error=f"{type(exc).__name__}: {exc}"))
