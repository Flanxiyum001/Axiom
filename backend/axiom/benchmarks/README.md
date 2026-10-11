# Benchmark Datasets and Inference Benchmarking

Defines, loads, and serves benchmark datasets to the Experiment Runner.
Datasets stay independent of providers and evaluators.

## Dataset components

```text
Dataset JSON → Loader → BenchmarkDataset → adapters.case_to_request() → ExperimentRunner
```

- `models.py` — `BenchmarkDataset`, `BenchmarkCase`, and `CaseEvaluationConfig`.
- `loader.py` — `load_file`, `loads`, `load_dict`, and `load_example`; malformed input raises `BenchmarkLoadError`.
- `adapters.py` — conversion from dataset cases into runner requests.
- `registry.py` — named dataset registry with isolated copies.
- `datasets/example_benchmark.json` — general example dataset.
- `datasets/nemotron_prompt_ab_v1.json` — five fixed-answer cases for the exploratory Nemotron prompt A/B run.
- `inference_runner.py` — request-capped Token Factory inference benchmark, metrics, and regression report.

## Run the inference benchmark safely

From the repository root (after installing the project with `pip install -e '.[dev]'`):

```bash
# Dry-run only; this is the default and sends zero API requests.
python -m axiom.benchmarks.inference_runner

# Explicit opt-in for live Token Factory inference.
python -m axiom.benchmarks.inference_runner --live

# Two repetitions per variant require 20 requests for the bundled 5-case set.
python -m axiom.benchmarks.inference_runner --repetitions 2 --max-requests 20 --live
```

Live mode requires `NEBIUS_API_KEY` locally and reads `NEBIUS_BASE_URL`
and `NEBIUS_MODEL` from the environment (with safe defaults). Keep the key
in a local `.env` file; never commit it or include it in a report. The runner
checks the required request count against `--max-requests` before sending any
requests. The default cap is 10 requests, the hard cap is 40, and repetitions
are limited to 1-4. It uses a fixed temperature of 0.1 and never launches GPU
jobs. All CI tests use a fake client and make no external API calls.

The runner records request success, structured-output validity, exact-match
accuracy, latency, and token usage when returned by the provider. It writes a
JSON report under `artifacts/benchmarks/` unless `--output` is set. Existing
output files are never overwritten. Baseline and candidate differ only in
their prompt template; the model and request parameters are held constant.

## Interpretation and limitations

This is an exploratory, small fixed-answer benchmark—not a statistical
significance test or a general capability evaluation. Network/provider load
affects latency, exact-match accuracy only measures the bundled expected
answers, and missing token usage is reported as incomplete instead of being
silently filled. Review raw per-request measurements with the PASS/WARNING/FAIL
regression summary before drawing conclusions.

## Adding a dataset

Write JSON with `name` and `cases` (each with `id` and `input`, plus
optional `expected_output`, `metadata`, and `evaluation`), then load it
with `load_file`. No core dataset-model changes are required.
