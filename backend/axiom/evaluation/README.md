# Evaluation Framework

Takes structured `ExperimentResult` objects from the Experiment Runner and
scores them with pluggable evaluators. Evaluation never modifies its input.

## Flow

```text
ExperimentResult → EvaluationFramework → Evaluator(s) → EvaluationResult
```

## Layout

- `base.py` — `Evaluator` interface: a `name` plus `evaluate(result)`.
- `models.py` — `EvaluatorOutcome` (one verdict) and `EvaluationResult`
  (verdicts plus an overall pass/fail/inconclusive flag).
- `framework.py` — `EvaluationFramework`: owns evaluators, runs them all,
  aggregates. Register more any time with `register()`; no core changes needed.
- `evaluators.py` — built-ins: `LatencyEvaluator`, `TokenUsageEvaluator`,
  `ResponseEvaluator`.

## Semantics

- Overall `passed` is `False` if any outcome fails, `True` if at least one
  passes and none fail, otherwise `None` (inconclusive).
- A crashing evaluator (or one returning the wrong type) becomes a failed
  outcome with the error captured; the run continues.
- `TokenUsageEvaluator` without usage data is inconclusive, not failed.
- Non-`ExperimentResult` input raises `TypeError`.

## Adding an evaluator

Subclass `Evaluator`, set `name`, implement `evaluate`, then `register()` it.
No framework code changes required. See `evaluators.py` for examples.
