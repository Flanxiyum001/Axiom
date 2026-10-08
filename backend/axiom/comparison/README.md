# Run Comparison

Compares two persisted benchmark runs read-only: metadata, aggregate
metrics with direction-aware verdicts, and case-level diffs matched by
stable case IDs.

## Flow

```text
BenchmarkRun A + BenchmarkRun B → compare_runs() → RunComparison
```

## Layout

- `models.py` — `MetricVerdict` (improved, regressed, unchanged, unknown),
  `MetricDelta`, `CaseComparison`, `MetadataDifference`, `RunComparison`.
- `comparison.py` — `compare_runs()`, `compare_metric()`,
  `KNOWN_DIRECTIONS`, `IncompatibleRunsError`.

## Semantics

- Different benchmark datasets refuse comparison loudly; everything else
  degrades to structured unknowns, missing lists, and warnings.
- Percentages divide by the baseline magnitude and stay empty when the
  baseline is zero; deltas and verdicts still hold.
- Unknown directions never guess: the verdict is unknown, never assumed.
- Custom metric directions merge over the built-ins via `directions=`.
- Inputs are never mutated; the comparison is a new object.
