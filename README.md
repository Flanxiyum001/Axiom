# AXIOM

AXIOM is an autonomous AI research and experimentation platform designed to accelerate scientific discovery and optimization.

## Core Research Loop

AXIOM operates on a continuous, evidence-based experimental loop:

1.  **Research Objective**: Define a measurable goal (e.g., "Reduce inference latency by 20%").
2.  **Hypothesis**: Generate a testable hypothesis.
3.  **Experiment Plan**: Create a structured plan to test the hypothesis.
4.  **Experiment Code**: Generate the necessary code for the experiment.
5.  **Execute Experiment**: Run the experiment in an isolated, safe environment.
6.  **Collect Metrics**: Gather objective performance data.
7.  **Evaluate Results**: Compare metrics against the baseline.
8.  **Analyze Evidence**: Determine if the hypothesis was supported.
9.  **Generate Next Hypothesis**: Use findings to inform the next iteration.

## MVP Scope

The initial MVP focuses on **ML model inference optimization**.

## Planned Architecture

- **Backend**: Python, FastAPI, Pydantic.
- **Agent Layer**: Specialized agents (Researcher, Planner, Analyst) for orchestration.
- **Experiment Layer**: Modular runner, evaluator, and sandbox for safe execution.
- **Memory**: Persistent store for experiment history and findings.
- **Frontend**: Next.js (planned).

## LLM Provider Integration

AXIOM supports two LLM providers:

### Mock Provider (Default)

- **Purpose**: Deterministic, offline testing without API keys
- **Usage**: Perfect for unit tests and development
- **Configuration**: `AXIOM_LLM_PROVIDER=mock`

### Nebius Token Factory Provider

- **Purpose**: Real LLM inference using Nebius Token Factory OpenAI-compatible API
- **Models**: Supports Nemotron models and other OpenAI-compatible models
- **Features**:
  - Structured output via JSON schema enforcement
  - Automatic retries with exponential backoff
  - Context truncation to prevent prompt overflow
  - Comprehensive error handling
- **Configuration**: `AXIOM_LLM_PROVIDER=nebius`
- **Required Environment Variables**:
  - `NEBIUS_API_KEY`: Your Nebius Token Factory API key
  - `NEBIUS_BASE_URL`: API base URL (default: `https://api.tokenfactory.nebius.com/v1/`)
  - `NEBIUS_MODEL`: Model identifier (default: `meta-llama/Meta-Llama-3.1-70B-Instruct`)


## Running Modes

AXIOM supports three distinct execution modes:

### A. Local Mock Mode
- **Provider**: `mock`
- **Behavior**: Deterministic, offline, no network calls. Used for unit tests, CI, rapid iteration.
- **Setup**: No environment variables required.

### B. Real Nebius LLM Mode
- **Provider**: `nebius`
- **Behavior**: Real LLM inference via the Nebius Token Factory (Nemotron or other OpenAI‑compatible models). Experiment execution remains deterministic (mock), only the reasoning layer is real.
- **Prerequisites**:
  1. Obtain a Nebius Token Factory API key.
  2. Populate `.env` (or export) with `NEBIUS_API_KEY`, optionally `NEBIUS_BASE_URL` and `NEBIUS_MODEL`.
  3. Set `AXIOM_LLM_PROVIDER=nebius`.
- **Safety**: Scripts check for required env vars and exit gracefully with a clear message if they are missing. No API keys are printed.

### C. Future Nebius AI Cloud GPU Experiment Execution
- **Goal**: Run actual GPU‑accelerated experiments on Nebius AI Cloud.
- **Status**: Not yet implemented. The current codebase only runs mock experiment code; real GPU execution will be added in a future release.

## Model ID

If a verified Nemotron model is available, update the following placeholder with the exact model identifier:

```
NEBIUS_MODEL=<verified-model-id>
```

Until then, the default model identifier is `meta-llama/Meta-Llama-3.1-70B-Instruct` as defined in `backend/config.py`.

## Development Setup

1.  Clone the repository.
2.  Create a virtual environment: `python -m venv .venv`
3.  Activate the environment.
4.  Install dependencies: `pip install -e .`
5.  Set up environment variables using `.env.example`.

## Project Status

Foundational repository setup with mock provider and Nebius integration ready.
