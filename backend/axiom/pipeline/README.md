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
