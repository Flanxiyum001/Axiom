# Experiment Execution

Runs one experiment request against a `ReasoningProvider` and returns
a structured result. Also hosts the registry of reusable benchmark example
definitions.

## Flow

```text
ExperimentRequest → ExperimentRunner(provider).run(request, output_type) → ExperimentResult
```

## Layout

- `runner.py` — `ExperimentRequest` (system, prompt, context),
  `ExperimentResult` (output, status, latency, provider/model, token fields,
  error, timestamps), and `ExperimentRunner`. Provider problems (errors,
  garbage or missing output) become `FAILED` results instead of raising.
- `registry.py` — named `ExperimentExample` definitions (code plus baseline
  and candidate environments) for reusable benchmark workloads.

## Semantics

- The runner is generic over any Pydantic output schema and records the
  calling `output_type` contract via validation.
- Token fields stay unset until a provider reports usage.
