"""Recording: capture pipeline output as a self-describing benchmark run."""

from __future__ import annotations

from axiom.domain.models import utcnow
from axiom.pipeline.models import PipelineResult
from axiom.runs.models import BenchmarkRun, BenchmarkRunStatus, ExecutionConfig


def record_run(
    result: PipelineResult,
    *,
    system: str = "",
    output_schema: str = "",
    dataset_description: str = "",
    evaluator_names: list[str] | None = None,
    max_concurrency: int = 1,
    fail_fast: bool = False,
    seed: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    max_tokens: int | None = None,
    extra: dict[str, str] | None = None,
) -> BenchmarkRun:
    """Freeze a pipeline outcome with derived and supplied configuration."""
    if not isinstance(result, PipelineResult):
        raise TypeError(f"Expected PipelineResult, got {type(result).__name__}")
    providers = sorted({record.experiment.provider for record in result.records})
    models = sorted(
        {
            record.experiment.model
            for record in result.records
            if record.experiment.model is not None
        }
    )
    if evaluator_names is None:
        evaluator_names = sorted(
            {
                outcome.evaluator
                for record in result.records
                for outcome in record.evaluation.outcomes
            }
        )
    starts = [record.experiment.started_at for record in result.records]
    ends = [
        record.experiment.completed_at
        for record in result.records
        if record.experiment.completed_at is not None
    ]
    now = utcnow()
    if result.records and not result.failures:
        status = BenchmarkRunStatus.COMPLETED
    elif result.records:
        status = BenchmarkRunStatus.PARTIAL
    else:
        status = BenchmarkRunStatus.FAILED
    return BenchmarkRun(
        status=status,
        config=ExecutionConfig(
            dataset=result.benchmark,
            dataset_description=dataset_description,
            case_ids=[record.case_id for record in result.records]
            + [failure.case_id for failure in result.failures],
            label=result.label,
            system=system,
            output_schema=output_schema,
            providers=providers,
            models=models,
            evaluator_names=list(evaluator_names),
            max_concurrency=max_concurrency,
            fail_fast=fail_fast,
            seed=seed,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            extra=dict(extra or {}),
        ),
        records=list(result.records),
        failures=list(result.failures),
        report=result.report,
        started_at=min(starts) if starts else now,
        completed_at=max(ends) if ends else now,
    )
