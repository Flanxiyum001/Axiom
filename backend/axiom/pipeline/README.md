# Experiment Pipeline

Runs benchmark datasets end to end: cases through the Experiment Runner,
results through the Evaluation Framework, records through Aggregation.

## Flow

```text
BenchmarkDataset → case_to_request() → runner.run() → framework.evaluate()
→ CaseRecord per case → aggregate_benchmark() → PipelineResult
```

## Layout

- `models.py` — `CaseFailure` (case id, stage, error, optional experiment)
  and `PipelineResult` (benchmark, label, report, records, failures).
- `pipeline.py` — `ExperimentPipeline`: binds an existing runner and
  framework. No provider, benchmark, or evaluator logic lives here.

## Parallel execution

`max_concurrency` bounds how many cases run at once (default `1`, i.e.
sequential, preserving existing behavior). Values above 1 run cases on a
thread pool with exactly that many workers: no unbounded task creation, and
large datasets still respect the limit. The default parallel value is `4`,
conservative enough for API rate limits while helping I/O-bound provider
calls; tune per provider.

Records always reassemble in dataset order, so completion order never affects
association or aggregation. Per-case failures still record without stopping
siblings; `fail_fast` cancels pending work and re-raises instead. Providers
and evaluators must be thread-safe; all built-in components are stateless
and safe to share across workers. Zero or negative limits, booleans, and
non-integers raise `ValueError` at construction.

## Semantics

- Every case becomes either a `CaseRecord` or a `CaseFailure` naming its
  stage (`run` or `evaluate`); failures never stop siblings by default.
- `fail_fast=True` re-raises the first unexpected error instead.
- Failed experiment results still flow through evaluation and aggregation,
  so gaps stay visible in the report.
- Evaluate-stage failures keep the experiment on the `CaseFailure`, so no
  measured result is ever discarded.
- A report exists when at least one case produces a `CaseRecord`, including
  cases from failed experiment results.
- Per-case `evaluation` budgets travel as data and are not yet translated
  into evaluator parameters; that wiring is a follow-up.
- Non-dataset input raises `TypeError`.
