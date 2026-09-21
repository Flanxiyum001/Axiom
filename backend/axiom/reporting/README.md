# Benchmark Reporting

Turns paired experiment and evaluation results into comparable benchmark
reports. Aggregation is independent of providers, datasets, and evaluators:
it only reads outcome scores and verdicts.

## Flow

```text
CaseRecords → aggregate_benchmark() → BenchmarkReport → format_text()
BenchmarkReport + BenchmarkReport → compare_reports() → ComparisonReport
```

## Layout

- `models.py` — `CaseRecord` (case id plus its experiment and evaluation
  results), `EvaluatorSummary` (score statistics plus verdict counts),
  `BenchmarkReport`, `MetricComparison`, `ComparisonReport`.
- `aggregation.py` — `aggregate_benchmark`, `compare_reports`, `format_text`.
  Non-finite scores are skipped so one bad measurement cannot poison a mean.

## Semantics

- Summaries group by evaluator name across all records of one benchmark.
- Overall input is never mutated; every record is preserved in the report.
- `label` names the experiment configuration, enabling comparison runs.
- Comparison covers evaluators present on both sides, by mean shift.
