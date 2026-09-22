# Experiment Layer

The Experiment Layer turns benchmark datasets into comparable benchmark
reports through four independent stages: run, evaluate, aggregate, orchestrate.
Each stage is usable on its own; the pipeline only wires them together.

Package guides with module-level detail live alongside the code:
[experiments](../backend/axiom/experiments/README.md),
[evaluation](../backend/axiom/evaluation/README.md),
[benchmarks](../backend/axiom/benchmarks/README.md),
[reporting](../backend/axiom/reporting/README.md),
[pipeline](../backend/axiom/pipeline/README.md).

## Architecture

```text
Benchmark Dataset
→ Dataset Loader            (benchmarks/loader.py)
→ Experiment Runner         (experiments/runner.py)
→ Experiment Results
→ Evaluation Framework      (evaluation/framework.py)
→ Evaluation Results
→ Aggregation               (reporting/aggregation.py)
→ Benchmark Report
```

| Component | Responsibility | Boundary |
|---|---|---|
| Benchmark dataset | Declares cases: input, optional reference answer, metadata, evaluator tuning as plain data | Knows nothing about providers or evaluators |
| Dataset loader | Reads files/JSON/mappings, validates, rejects bad data as `BenchmarkLoadError` | Only failure type callers handle is `BenchmarkLoadError` |
| Adapter | Converts one case into runner input (`input` → prompt, `metadata` → context) | Only place datasets and the runner meet |
| Experiment Runner | Executes one request against a `ReasoningProvider`, times it, records metadata | Never raises for provider problems; returns `FAILED` results instead |
| Evaluation Framework | Runs registered evaluators over one result, aggregates verdicts | Never mutates its input; evaluator crashes become failed outcomes |
| Evaluators | One metric each (latency, token usage, response content) | Added via `register()`; no framework changes |
| Aggregation | Groups records by benchmark, summarizes scores per evaluator, compares runs | Reads only outcome scores and verdicts |
| Pipeline | Per-case orchestration: run → evaluate → record, then aggregate | Holds no provider, benchmark, or evaluator logic |

## Data flow

1. `load_example()` (or `load_file`/`loads`/`load_dict`) produces a validated
   `BenchmarkDataset`.
2. `case_to_request(case)` produces an `ExperimentRequest` (system, prompt,
   context).
3. `ExperimentRunner(provider).run(request, output_type=...)` produces an
   `ExperimentResult`: validated output (or `None`), status, latency,
   provider/model info, token fields, error, timestamps.
4. `EvaluationFramework([...]).evaluate(result)` produces an
   `EvaluationResult`: one `EvaluatorOutcome` per evaluator plus an overall
   pass/fail/inconclusive flag.
5. Pairs become `CaseRecord`s (validated to reference the same experiment),
   and `aggregate_benchmark(name, records)` produces a `BenchmarkReport`
   with per-evaluator statistics and every record preserved.
6. `compare_reports(baseline, candidate)` diffs shared evaluators by mean
   shift; `format_text(report)` renders the human-readable shape.
7. `ExperimentPipeline(runner, framework).run(dataset, output_type=...)`
   performs steps 2–5 for every case and returns a `PipelineResult`
   (report, records, per-stage failures).

## How to create a new experiment

Build an `ExperimentRequest` and run it through `ExperimentRunner` with any
`ReasoningProvider` and any Pydantic output schema:

```python
runner = ExperimentRunner(provider)
result = runner.run(
    ExperimentRequest(system="Be concise.", prompt="Summarize this.", context={}),
    output_type=MySchema,
)
```

`result.status` tells you whether it worked; `result.error` explains failures.
The runner is generic, so new experiments mean new prompts and schemas, never
runner changes.

## How to create a new benchmark dataset

Write JSON with a `name` and `cases` (each needs `id` and `input`; optional
`expected_output`, `metadata`, and `evaluation` budgets), then load and
optionally register it:

```python
dataset = load_file("my_benchmark.json")
register(dataset)
```

See `backend/axiom/benchmarks/datasets/example_benchmark.json` and run the
worked example below. Note: per-case `evaluation` budgets travel as data for
now; the pipeline does not yet translate them into evaluator parameters.

## How to create a new evaluator

Subclass `Evaluator`, set `name`, implement `evaluate`, register it:

```python
class FreshnessEvaluator(Evaluator):
    name = "freshness"

    def evaluate(self, result):
        ...
        return EvaluatorOutcome(evaluator=self.name, passed=..., score=...)
```

The framework deep-copies the input per evaluator, so evaluators cannot
corrupt each other or the original. Crashes and wrong return types become
failed outcomes automatically.

## How results are represented

- **Experiment results** (`ExperimentResult`): output plus status, latency,
  provider/model, error, and timestamps. Token usage fields exist but stay
  unset until a provider reports usage through a future interface extension.
- **Evaluation results** (`EvaluationResult`): the evaluated experiment plus
  one outcome per evaluator and an overall flag (`False` if anything failed,
  `True` if something passed and nothing failed, else inconclusive).
- **Benchmark reports** (`BenchmarkReport`): benchmark name, config label,
  per-evaluator summaries (scored count, mean, min, max, verdict tallies),
  and all preserved records.

## How errors and failed cases are represented

- Provider problems → `ExperimentResult` with `status=FAILED` and `error`.
- Evaluator crashes → failed `EvaluatorOutcome` with the error captured.
- Bad dataset data → `BenchmarkLoadError` (never raw OS/validation errors).
- Bad aggregation input (empty records, duplicate case ids, cross-benchmark
  comparison) → `AggregationError`.
- Pipeline case problems → `CaseFailure` with case id, stage (`run` or
  `evaluate`), error, and the measured experiment when one exists.
- Programmer errors (wrong input types) → `TypeError`.

Failed experiments still flow through evaluation and aggregation, so reports
show gaps instead of silently dropping cases.

## Extending without modifying core

- New provider → implement `ReasoningProvider`.
- New output schema → pass any Pydantic model as `output_type`.
- New evaluator → subclass `Evaluator`, `register()` it.
- New dataset → JSON file, `load_file`, `register()`.
- New orchestration → reuse the pieces; the pipeline itself stays thin.

## Worked example

`experiments/examples/end_to_end_benchmark.py` runs the complete flow with a
deterministic mock provider (no credentials needed):

```text
PYTHONPATH=backend python experiments/examples/end_to_end_benchmark.py
```

It loads the bundled dataset, runs each case, evaluates latency and response
content, aggregates, and prints the final report.
