# Benchmark Datasets

Defines, loads, and serves benchmark datasets to the Experiment Runner.
Datasets stay independent of providers and evaluators.

## Flow

```text
Dataset JSON → Loader → BenchmarkDataset → adapters.case_to_request() → ExperimentRunner
```

## Layout

- `models.py` — `BenchmarkDataset`, `BenchmarkCase`, `CaseEvaluationConfig`.
  Cases carry input, an optional reference answer, string metadata, and
  optional evaluator tuning (budgets, minimum length) as plain data.
- `loader.py` — `load_file`, `loads`, `load_dict`, `load_example`. Every
  failure mode (missing file, bad JSON, undecodable bytes, schema violation,
  duplicate ids) raises `BenchmarkLoadError`, never a raw OS, Unicode, or
  validation exception.
- `adapters.py` — `case_to_request`, the runner-consumption boundary. Models
  stay runner-neutral; conversion lives here.
- `registry.py` — `register`, `get_dataset`, `list_datasets`. Snapshots on
  insert and returns isolated copies so callers cannot mutate shared state.
- `datasets/example_benchmark.json` — bundled example in the documented format.

## Adding a dataset

Write JSON with `name` and `cases` (each with `id` and `input`, plus
optional `expected_output`, `metadata`, `evaluation`), load it, and register
it. No core code changes required.
