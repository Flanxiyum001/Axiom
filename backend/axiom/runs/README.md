# Benchmark Runs

Persists complete benchmark executions for traceability and analysis.
Storage stays behind an abstraction; the default backend is local JSON files.

## Flow

```text
PipelineResult → record_run() → BenchmarkRun → RunStore.save()
RunStore.load(run_id) → BenchmarkRun
```

## Layout

- `models.py` — `BenchmarkRun` (id, status, config, records, failures,
  report, timestamps), `ExecutionConfig` (dataset, providers, models,
  evaluator names, concurrency, model parameters), `BenchmarkRunStatus`
  (pending, running, completed, partial, failed).
- `recording.py` — `record_run()`: freezes a pipeline outcome, deriving
  providers, models, evaluators, case ids, timestamps, and status.
- `store.py` — `RunStore` interface (`save`, `load`, `exists`, `list_runs`)
  plus `FileRunStore` (one indented JSON file per run, atomic writes).
  Missing runs raise `RunNotFoundError`; backend failures raise
  `RunStoreError`. Listings skip foreign files and ID/filename mismatches
  with a warning, while unreadable files and direct loads stay strict.

## Semantics

- Status derives from pipeline completion: all cases recorded is completed,
  some lost to unexpected errors is partial, none recorded is failed.
  Pending and running exist for live tracking.
- Unknown model parameters stay `None`; the run never claims more
  reproducibility than its configuration actually holds.
- Run IDs use the shared `brun_` prefixed generator and never timestamps.
