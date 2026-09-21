# Benchmark Datasets

Defines, loads, and serves benchmark datasets to the Experiment Runner.
Datasets stay independent of providers and evaluators.

## Flow

```text
Dataset JSON → Loader → BenchmarkDataset → case.to_request() → ExperimentRunner
```

## Layout

- `models.py` — `BenchmarkDataset`, `BenchmarkCase`, `CaseEvaluationConfig`.
  Cases carry input, an optional reference answer, string metadata, and
  optional evaluator tuning (budgets, minimum length) as plain data.
- `loader.py` — `load_file`, `loads`, `load_dict`, `load_example`. Every
  failure mode (missing file, bad JSON, schema violation, duplicate ids)
  raises `BenchmarkLoadError`, never a raw OS or validation exception.
- `registry.py` — `register`, `get_dataset`, `list_datasets`. Returns
  isolated copies so callers cannot mutate shared state.
- `datasets/example_benchmark.json` — bundled example in the documented format.

## Adding a dataset

Write JSON with `name` and `cases` (each with `id` and `input`, plus
optional `expected_output`, `metadata`, `evaluation`), load it, and register
it. No core code changes required.
