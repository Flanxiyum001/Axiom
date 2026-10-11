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
  See [docs/experiment-layer.md](docs/experiment-layer.md) for the architecture
  guide and [experiments/examples/end_to_end_benchmark.py](experiments/examples/end_to_end_benchmark.py)
  for a runnable end-to-end demo.
- **Memory**: Persistent store for experiment history and findings.
- **Frontend**: Next.js (planned).

## LLM Provider Integration

AXIOM supports two LLM providers:

### Mock Provider (Default)

- **Purpose**: Deterministic, offline testing without API keys
- **Usage**: Perfect for unit tests and development
- **Configuration**: `AXIOM_LLM_PROVIDER=mock` (compatible with the canonical API, where `mock` maps to the deterministic `echo` provider)

### Nebius Token Factory Provider

- **Purpose**: Real LLM inference using Nebius Token Factory OpenAI-compatible API
- **Models**: Supports Nemotron models and other OpenAI-compatible models
- **Features**:
  - Structured output via JSON schema enforcement
  - Automatic retries with exponential backoff
  - Context truncation to prevent prompt overflow
  - Comprehensive error handling
- **Configuration**: `AXIOM_REASONING_PROVIDER=nebius` (canonical API) or `AXIOM_LLM_PROVIDER=nebius` (compatibility alias)
- **Required Environment Variables**:
  - `NEBIUS_API_KEY`: Your Nebius Token Factory API key
  - `NEBIUS_BASE_URL`: API base URL (default: `https://api.tokenfactory.nebius.com/v1/`)
  - `NEBIUS_MODEL`: Model identifier (canonical API default: `nvidia/nemotron-3-super-120b-a12b`)


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
  3. Set `AXIOM_REASONING_PROVIDER=nebius` (or use `AXIOM_LLM_PROVIDER=nebius` for compatibility). The canonical API prioritizes `AXIOM_REASONING_PROVIDER` when both are set.
- **Safety**: Scripts check for required env vars and exit gracefully with a clear message if they are missing. No API keys are printed.

### C. Nebius AI Cloud GPU Experiment Execution
- **Status**: **Experimental; end-to-end execution is not verified.** The repository includes a `NebiusGPUExecutor` and a `RealNebiusJobClient` for the Nebius AI Cloud job API. To opt into that execution path, set `AXIOM_EXECUTOR_BACKEND=nebius_gpu`; local execution remains the default. The separate `NebiusStorageArtifactClient` and `integrate_nebius_artifact_retrieval()` helper provide S3-compatible metrics retrieval, but the mounted-output-to-object-key mapping is still an unverified assumption.
- **Verification**: No real GPU job or live object-storage request has verified the end-to-end path. Job submission, status polling, output mounting, object-key mapping, and artifact retrieval must be validated with an explicitly authorized smoke test before describing cloud execution as production-ready.

## Model ID

The canonical research-loop settings in `backend/axiom/config.py` default to `nvidia/nemotron-3-super-120b-a12b`. Set `NEBIUS_MODEL` explicitly when selecting a different model. The legacy `backend/config.py` module has separate settings and is not the source of defaults for the canonical research-loop path.

## Development Setup

1.  Clone the repository.
2.  Create a virtual environment: `python -m venv .venv`
3.  Activate the environment.
4.  Install dependencies: `pip install -e '.[dev]'`
5.  Copy `.env.example` to `.env` and set `NEBIUS_API_KEY` when using the real provider.
6.  Start the canonical API from the repository root: `uvicorn backend.main:app --reload`.
7.  Open `http://127.0.0.1:8000/docs` to explore the API. The canonical API entry point loads `.env` without overriding exported shell variables.

## Project Status

Foundational repository setup with mock provider and Nebius integration ready.
