# AXIOM

AXIOM is an experimental research workspace for recording the path from an optimization question to a hypothesis, an A/B experiment, a metric comparison, and an evidence-based conclusion. A FastAPI backend coordinates the research stages; a Next.js frontend shows the plan, runs, provenance, and saved history.

**Scope:** the working demonstrations use synthetic CPU arithmetic rather than model-inference benchmarks. A separate live NVIDIA Nemotron 3 Super integration generates an experiment *proposal* through Nebius Token Factory. Neither demonstration establishes an actual model speedup, quantization result, TensorRT optimization, or GPU benchmark.

[Open the research workspace](https://axiom-frontend-demo.up.railway.app/#objective-workspace) · [Try the live Nemotron proposal](https://axiom-frontend-demo.up.railway.app/showcase)

## Why this exists

Evaluating an optimization idea requires more than comparing two numbers. An experiment should preserve the question, intervention, implementation, settings, results, and limitations together. AXIOM provides a small reference workflow for inspecting those parts in one place, while distinguishing a proposed mechanism from what the executed script can actually support.

It is intended for developers exploring repeatable ML experiment workflows, not for untrusted public code execution or validated production benchmarking.

## Implemented capabilities

| Capability | Current behavior |
| --- | --- |
| Objectives and history | Create and list objectives, execute research iterations, inspect their results and history through FastAPI and Next.js. The standard local configuration saves records to SQLite. |
| Research stages | Researcher, Planner, deterministic Evaluator, and Analyst coordinate a hypothesis, experiment specification, comparison, and conclusion. |
| Offline reasoning | The default Echo provider produces deterministic reasoning without model credentials. |
| Local execution | An experiment engine validates specifications and runs baseline/candidate Python subprocesses. This is a trusted-local-development tool, **not a secure sandbox**. |
| Hosted research demo | A fixed objective runs a built-in synthetic CPU task with Echo reasoning. The public frontend uses an allowlisted proxy to a private, constrained API. History is shared and held in memory until the demo process restarts. |
| Live model showcase | A separate Next.js server route requests a fixed, structured experiment proposal from NVIDIA Nemotron 3 Super via Nebius Token Factory. It validates the response and does not execute model-generated code. Responses may be cached during a per-process cooldown. |
| Optional backend reasoning | The local research loop can be configured to use the Nebius provider instead of Echo. Its full live end-to-end behavior has not been independently validated. |

### The research flow

1. The API parses an objective and stores it.
2. The Researcher proposes a hypothesis; the Planner builds an experiment plan and specification.
3. The engine validates the specification and collects baseline and candidate script output through the selected executor.
4. The deterministic evaluator compares reported metrics. The Analyst records an interpretation and limitations.
5. SQLite retains the objective, plans, runs, evaluations, and evidence for later inspection.

The local engine reads metric JSON emitted by experiment code. Those values are **not independently attested performance measurements**: code can report misleading numbers, and an intervention label is not proof that a feature was implemented. The known Echo intervention changes the amount of synthetic arithmetic. Unknown or conflicting mechanisms receive an insufficient-evidence conclusion.

The public demo uses a more restrictive executor: it ignores executable specification code and times only a built-in arithmetic loop. Its CPU timing values vary by host load and do not represent real ML inference latency.

## Architecture

```text
frontend/app/page.jsx                 Next.js research dashboard
frontend/app/showcase/page.jsx        Live-model proposal interface
frontend/app/api/showcase/nemotron/   Bounded server-side Token Factory request
frontend/lib/judge-demo-proxy.mjs     Allowlisted proxy for the fixed hosted demo

backend/main.py                       FastAPI application and CORS configuration
backend/axiom/api/routes.py           Objective, run and history endpoints
backend/axiom/services/research_loop.py
                                      Research stage orchestration
backend/axiom/execution/              Validation, execution, deterministic evaluation
backend/axiom/memory/sqlite_repo.py   Research record storage
backend/axiom/demo.py                 Fixed synthetic CPU demonstration
backend/llm/nebius.py                 Optional Token Factory reasoning provider
```

The experiment executor and the reasoning provider are separate choices. Selecting Nemotron for *reasoning* does not turn the CPU workload into a GPU or model-inference benchmark. The experimental Nebius GPU execution adapter is not verified end to end; it is not part of the hosted demonstration.

**Stack:** Python, FastAPI, Pydantic, SQLite, Next.js, React, Nebius Token Factory, NVIDIA Nemotron 3 Super, pytest, Node's test runner, and Playwright.

## Run locally

Prerequisites: **Python 3.11 or 3.12**, **Node.js 22**, and npm. The project uses an ordinary npm install; no committed frontend lockfile is currently provided.

From the repository root, install the backend dependencies:

```sh
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

On Windows PowerShell, activate with `./.venv/Scripts/Activate.ps1` and use `python -m pip install -e ".[dev]"`.

For an offline local backend, run:

```sh
export AXIOM_REASONING_PROVIDER=echo
export AXIOM_EXECUTOR_BACKEND=local
export PYTHON_DOTENV_DISABLED=1
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

PowerShell equivalent:

```powershell
$env:AXIOM_REASONING_PROVIDER = "echo"
$env:AXIOM_EXECUTOR_BACKEND = "local"
$env:PYTHON_DOTENV_DISABLED = "1"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm install --no-audit --no-fund
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The default backend URL is `http://127.0.0.1:8000`; FastAPI documentation is at `http://127.0.0.1:8000/docs`. The sample objective is `Reduce model inference latency by 20%`. You can create it, run an iteration, examine the experiment record, and reload the saved history.

Local records default to `axiom.db` and `artifacts/`. Override them with `AXIOM_DB_PATH` and `AXIOM_ARTIFACT_ROOT`. **Only execute trusted local experiments on a disposable, unprivileged system.** The AST validator and subprocess timeouts do not provide filesystem or network isolation.

## Nebius Token Factory configuration

The backend defaults to Echo. For optional live reasoning, select `AXIOM_REASONING_PROVIDER=nebius` and set `NEBIUS_API_KEY` **only in the backend process environment** or a locally ignored `.env`. The canonical defaults are:

```dotenv
AXIOM_REASONING_PROVIDER=nebius
AXIOM_EXECUTOR_BACKEND=local
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
NEBIUS_MODEL=nvidia/nemotron-3-super-120b-a12b
NEBIUS_API_KEY=replace-with-your-own-token
```

Copy `.env.example` for a local template. Remove any previously exported Echo override; unset `PYTHON_DOTENV_DISABLED` if you want local dotenv loading. Live calls can incur provider charges.

A one-request, provider-only verification command is available:

```sh
python -m scripts.smoke_nebius_reasoning --live
```

This checks a structured model response and makes at most one external request; it does **not** execute an experiment. The live showcase at `/showcase` is a separate, server-side Next.js integration using `AXIOM_NEBIUS_SHOWCASE_ENABLED=1` and `NEBIUS_API_KEY` in the **frontend server environment**, never in `NEXT_PUBLIC_*` variables.

For deployment, keep the unrestricted local executor API private. The hosted synthetic API uses `AXIOM_DEMO_MODE=1` with a fixed executor behind a same-origin proxy and private Railway networking. The live-showcase endpoint is independent of that backend. The demo's process-local limits are not a substitute for edge-level abuse protection.

## Tests

From the repository root:

```sh
python -m pytest tests/ -q
```

From `frontend/`:

```sh
npm test
npm run build
npx playwright install chromium
npm run test:smoke
```

The browser smoke suite starts local Echo and Next.js servers on ports 8100 and 3100, runs a research objective, verifies the provenance/history view, and tests the showcase with a **mocked** provider response. It does not spend Token Factory credits. A second constrained-demo browser configuration is available via `npm run test:smoke:demo`. The tests use isolated configuration and temporary storage; set `AXIOM_TEST_PYTHON` if the test runner cannot find the desired Python interpreter.

## Limitations

- The current example executes synthetic arithmetic; it does not benchmark a real model or GPU.
- Locally executed generated Python is not sandboxed; stdout-derived metric values are not independently trusted measurements.
- The hosted research demonstration uses shared, in-memory state that resets when the backend restarts.
- The public Token Factory showcase returns a proposal, not a completed experiment. Its cooldown and cache are scoped to a single server process.
- Nebius AI Cloud GPU execution and full live-reasoning research runs have not been verified end to end.

See [the pipeline assessment](docs/pipeline-audit.md) for measurement caveats and [the experiment-layer guide](docs/experiment-layer.md) for extension points.

## License

Apache License 2.0. See [LICENSE](LICENSE).
