"""Experiment pipeline: dataset cases through runner, evaluation, aggregation."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from axiom.benchmarks.adapters import case_to_request
from axiom.benchmarks.models import BenchmarkCase, BenchmarkDataset
from axiom.domain.interfaces import T
from axiom.evaluation.framework import EvaluationFramework
from axiom.experiments.runner import ExperimentResult, ExperimentRunner
from axiom.pipeline.models import CaseFailure, PipelineResult
from axiom.reporting.aggregation import aggregate_benchmark
from axiom.reporting.models import CaseRecord

DEFAULT_MAX_CONCURRENCY = 1
RECOMMENDED_MAX_CONCURRENCY = 4


class _CaseError(Exception):
    """Unexpected per-case failure carrying its provenance."""

    def __init__(
        self,
        case_id: str,
        stage: str,
        cause: BaseException,
        experiment: ExperimentResult | None = None,
    ) -> None:
        """Capture where the case failed, why, and what was measured."""
        super().__init__(f"{case_id} failed at {stage}: {cause}")
        self.case_id = case_id
        self.stage = stage
        self.cause = cause
        self.experiment = experiment

    def to_failure(self) -> CaseFailure:
        """Represent the failure structurally without losing the experiment."""
        cause = self.cause
        return CaseFailure(
            case_id=self.case_id,
            stage=self.stage,
            error=f"{type(cause).__name__}: {cause}",
            experiment=self.experiment,
        )


class ExperimentPipeline:
    """Lightweight orchestration over runner, framework, and aggregation."""

    def __init__(
        self,
        runner: ExperimentRunner,
        framework: EvaluationFramework,
        *,
        fail_fast: bool = False,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        """Bind components; max_concurrency bounds parallel case execution."""
        if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int):
            raise ValueError(f"max_concurrency must be an integer, got {max_concurrency!r}")
        if max_concurrency < 1:
            raise ValueError(f"max_concurrency must be at least 1, got {max_concurrency}")
        self.runner = runner
        self.framework = framework
        self.fail_fast = fail_fast
        self.max_concurrency = max_concurrency

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
        if not dataset.cases:
            return PipelineResult(benchmark=dataset.name, label=label)
        if self.max_concurrency == 1:
            records, failures = self._run_sequential(dataset, output_type=output_type, system=system)
        else:
            records, failures = self._run_parallel(dataset, output_type=output_type, system=system)
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

    def _run_sequential(
        self,
        dataset: BenchmarkDataset,
        *,
        output_type: type[T],
        system: str,
    ) -> tuple[list[CaseRecord], list[CaseFailure]]:
        """Process cases one by one in dataset order."""
        records: list[CaseRecord] = []
        failures: list[CaseFailure] = []
        for case in dataset.cases:
            try:
                records.append(self._run_case(case, output_type=output_type, system=system))
            except _CaseError as err:
                if self.fail_fast:
                    raise err.cause
                failures.append(err.to_failure())
        return records, failures

    def _run_parallel(
        self,
        dataset: BenchmarkDataset,
        *,
        output_type: type[T],
        system: str,
    ) -> tuple[list[CaseRecord], list[CaseFailure]]:
        """Process a rolling window, reassembled in dataset order."""
        cases = dataset.cases
        records: dict[int, CaseRecord] = {}
        failures: dict[int, CaseFailure] = {}
        pending = iter(range(len(cases)))
        executor = ThreadPoolExecutor(
            max_workers=self.max_concurrency, thread_name_prefix="axiom-case"
        )
        abandoned = False
        try:
            in_flight: dict[Future, int] = {}
            for _ in range(min(self.max_concurrency, len(cases))):
                index = next(pending)
                in_flight[
                    executor.submit(self._run_case, cases[index], output_type=output_type, system=system)
                ] = index
            while in_flight:
                done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
                for future in done:
                    index = in_flight.pop(future)
                    try:
                        records[index] = future.result()
                    except _CaseError as err:
                        if self.fail_fast:
                            abandoned = True
                            for outstanding in in_flight:
                                outstanding.cancel()
                            executor.shutdown(wait=False, cancel_futures=True)
                            raise err.cause
                        failures[index] = err.to_failure()
                for _ in range(len(done)):
                    try:
                        nxt = next(pending)
                    except StopIteration:
                        break
                    in_flight[
                        executor.submit(self._run_case, cases[nxt], output_type=output_type, system=system)
                    ] = nxt
        finally:
            if not abandoned:
                executor.shutdown(wait=True)
        return [records[i] for i in sorted(records)], [failures[i] for i in sorted(failures)]

    def _run_case(
        self,
        case: BenchmarkCase,
        *,
        output_type: type[T],
        system: str,
    ) -> CaseRecord:
        """Run and evaluate one case; unexpected errors propagate with stage."""
        try:
            experiment = self.runner.run(case_to_request(case, system), output_type=output_type)
        except Exception as exc:
            raise _CaseError(case.id, "run", exc) from exc
        try:
            evaluation = self.framework.evaluate(experiment)
            return CaseRecord(case_id=case.id, experiment=experiment, evaluation=evaluation)
        except Exception as exc:
            raise _CaseError(case.id, "evaluate", exc, experiment) from exc
