# AXIOM

AXIOM turns an objective into a hypothesis, controlled experiment plan, executable Python, measured comparison, and saved analyst evidence. FastAPI serves a Next.js research dashboard. Licensed under [Apache 2.0](LICENSE).

**What works today:** Echo provides offline reasoning; Nebius/Nemotron can provide live reasoning. The dashboard planner generates **synthetic CPU workloads**, not real model-inference benchmarks. Echo's candidate reduces arithmetic loop iterations. A label such as `threads` or `precision` names a simulated intervention; it does not demonstrate threading, quantization, GPU throughput, or a model latency improvement.

## Fresh setup

Use Python **3.11 or 3.12** and Node.js **22**, matching CI. From the repository root:

```sh
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell instead:
# .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

For a credential-free backend, explicitly select Echo and local execution. These exported values override any local `.env` provider choice.

```sh
# macOS/Linux
export AXIOM_REASONING_PROVIDER=echo
export AXIOM_EXECUTOR_BACKEND=local
export PYTHON_DOTENV_DISABLED=1
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

PowerShell equivalent:

```powershell
$env:AXIOM_REASONING_PROVIDER='echo'
$env:AXIOM_EXECUTOR_BACKEND='local'
$env:PYTHON_DOTENV_DISABLED='1'
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd frontend
npm install --no-audit --no-fund
npm run dev
```

Open http://localhost:3000. The default API is http://127.0.0.1:8000; API docs are at `/docs`. Confirm **API connected** and provider **echo**. Enter `Reduce model inference latency by 20%`, click **Create objective**, select one iteration, then **Run research**. Inspect the hypothesis, measured baseline/candidate, analyst conclusion and provenance. Refresh the page to inspect persisted history. Default storage is `axiom.db` and `artifacts/`; set `AXIOM_DB_PATH` and `AXIOM_ARTIFACT_ROOT` to choose separate storage.

## Optional Nebius reasoning

Copy `.env.example` to `.env` locally, select `AXIOM_REASONING_PROVIDER=nebius`, and supply `NEBIUS_API_KEY` in your backend environment or local `.env`. Do not print the key. Unset `PYTHON_DOTENV_DISABLED` if you want the backend to load `.env`. Remove any exported Echo provider override before selecting Nebius in the file. Keep `AXIOM_EXECUTOR_BACKEND=local`.

Canonical defaults: base URL `https://api.tokenfactory.nebius.com/v1/`, model `nvidia/nemotron-3-super-120b-a12b`. Override with `NEBIUS_BASE_URL` and `NEBIUS_MODEL`. A Nebius run uses billable reasoning requests. It still executes synthetic experiments locally. `AXIOM_LLM_PROVIDER=mock` remains a compatibility alias for Echo; `AXIOM_REASONING_PROVIDER` takes precedence.

#### One-request Nemotron smoke test

The canonical research loop selects `backend.llm.nebius.NebiusLLMProvider` through
`LoopServices.from_settings()`. Its default is Echo; the Nebius provider sends an
OpenAI-compatible chat completion to Token Factory with the model from
`backend/axiom/config.py`. The opt-in check below calls that same provider once
with a small structured reply. It does not start the research loop, execute
generated Python, launch a GPU job, or write an experiment artifact.

1. Install dependencies from the repository root: `python -m pip install -e '.[dev]'`.
2. Put an authorized Token Factory key in the process environment as
   `NEBIUS_API_KEY` or in the repository-local, ignored `.env` file. Keep
   `NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/` and
   `NEBIUS_MODEL=nvidia/nemotron-3-super-120b-a12b` (their canonical defaults).
   Shell variables take precedence over `.env`.
3. Run `python -m scripts.smoke_nebius_reasoning --live` from the repository root.

The command prints only the provider name, requested model, response model, and
whether the structured marker was validated. It requires the response model to
match Nemotron exactly. A missing key, rejected credentials, rate limit,
timeout, malformed response, or model mismatch produces a nonzero exit and a
sanitized error. It makes at most one HTTP attempt, so a transient failure must
be retried manually. Do not paste the key into command-line arguments or share
the local `.env` file.

**Verification status (2026-10-19):** This checkout had no `NEBIUS_API_KEY` in
the environment or local `.env`, so a real Token Factory request could not be
performed here. The missing-key path and mocked provider tests can be checked
offline; a maintainer with authorized credentials must run the command above to
confirm live inference. One successful inference would verify Nemotron reasoning
only. The Echo demo's CPU arithmetic is synthetic and is not evidence of model
inference speedup, quantization, multithreading, or GPU performance.

Never put credentials in `NEXT_PUBLIC_*` variables or frontend files. Only the API base URL belongs in `NEXT_PUBLIC_AXIOM_API_URL`. For another frontend origin, configure backend `AXIOM_CORS_ORIGINS` as a comma-separated list of exact origins.

## Verification

```sh
python -m pytest tests/ -q
cd frontend
npm test
npm run build
```

Tests disable dotenv before application imports, reset configuration per test, and block external socket connections. Provider tests inject mocked clients. No live credential is needed. CI runs Python 3.11 and 3.12, frontend provenance tests, production build, and the browser smoke test.

Install Chromium once, with the Python virtual environment active:

```sh
cd frontend
npm install --no-audit --no-fund
npx playwright install chromium
npm run test:smoke
```

`npm run test:smoke` starts a local Echo backend on port 8100 and Next.js on 3100, uses a new temporary database/artifact directory, creates and runs an objective in Chromium, verifies API-derived evidence and provenance, and reloads saved history. It refuses to reuse existing servers. If Python is not on PATH, set `AXIOM_TEST_PYTHON` to the virtual environment's Python executable. Failures retain screenshots and traces in `frontend/test-results/`; `npx playwright show-trace <trace.zip>` opens a trace. Temporary smoke storage uses the OS temp directory and may be retained for diagnosis.

## Architecture and evidence boundaries

`backend/main.py` mounts the canonical routes in `backend/axiom/api/routes.py`. `LoopServices` connects Researcher -> Planner -> AST validator -> local executor -> deterministic evaluator -> Analyst -> SQLite. `axiom/` is an import shim pointing to `backend/axiom`. `frontend/app/page.jsx` consumes API responses and persisted history; `frontend/lib/provenance.mjs` derives display provenance.

Baseline and candidate execute the same Python code and parameters, with both mode environment variables forced to the appropriate condition. The executor parses metric JSON from process stdout; the evaluator computes the comparison without asking an LLM for measurement values. Generated code can still emit fabricated values: parsing stdout is **not independent measurement attestation**. Only the known Echo implementation is identified as a verified synthetic intervention. Unknown or conflicting implementations receive an insufficient-evidence analyst conclusion. Matching lever declarations do not prove an implementation. The dashboard distinguishes planned settings, spec parameters, execution environment, and measured metrics.

The AST validator is **not a secure sandbox**. Local execution uses subprocesses, temporary working directories, minimal environment, timeouts and best-effort POSIX resource limits. It does not isolate the host filesystem or network, and Windows does not supply POSIX resource limits. Run only trusted experiments on a disposable, unprivileged machine. Do not expose this unauthenticated local API to untrusted users. See [pipeline audit](docs/pipeline-audit.md) for remaining limitations and the smallest real-inference follow-up.

Nebius GPU execution exists as an experimental adapter; its submission, mounts, storage mapping and artifact retrieval are not verified end to end. Do not enable it for the offline demo or claim GPU benchmark results.

See the [2:40 demo script and fallback](docs/demo-walkthrough.md), [release report](docs/release-audit.md), and [experiment-layer guide](docs/experiment-layer.md).
