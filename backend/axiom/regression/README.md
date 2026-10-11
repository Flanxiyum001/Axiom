# Regression Detection

Detects benchmark regressions read-only from an existing run comparison.

## Flow

```text
BenchmarkRun baseline + BenchmarkRun candidate → compare_runs() → RunComparison
  → detect_from_comparison() → RegressionReport (PASS / WARNING / FAIL)
```

`detect_regressions(baseline, candidate, config)` is a convenience wrapper
that compares then evaluates in one call.

## Thresholds

- `RegressionConfig` holds global defaults plus `per_metric` overrides.
- Each metric supports absolute (`warn_abs` / `fail_abs`, applied to
  `abs(delta)`) and percentage (`warn_pct` / `fail_pct`, applied to
  `abs(percent)` where `percent = delta / abs(baseline) * 100`).
- Percent is a relative change against the baseline magnitude, not
  percentage points. Example: accuracy 90 → 87 gives delta -3 and
  percent -3.33%.
- Boundaries are inclusive: a magnitude `>=` the threshold triggers that
  level. Failure is checked before warning.
- Zero baselines yield no percent (comparison layer); only absolute
  thresholds apply there. No division path exists.
- Only `REGRESSED` verdicts (direction-aware, from the comparison layer)
  can warn or fail. Improved, unchanged, and unknown deltas are PASS.
- A regressed metric with configured thresholds below both levels is PASS
  (sub-threshold, tolerated). A regressed metric with no thresholds at
  all is WARNING (conservative default).

## Cases and overall status

- Shared cases reuse the same per-metric thresholds; a case takes the
  worst of its metrics.
- Baseline-only cases are WARNING (missing from candidate); candidate-only
  cases are PASS (informational). Both appear in the missing lists.
- Missing metrics (unknown deltas) are PASS with a reason and never fail.
- Overall status is deterministic: any FAIL → FAIL, else any WARNING →
  WARNING, else PASS.
- Inputs are never mutated; the report is a new object.
