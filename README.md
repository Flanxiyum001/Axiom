# AXIOM
### From an optimization question to an inspectable experiment

**AXIOM is an evidence-oriented ML research prototype.** It connects an optimization objective to a hypothesis, structured plan, baseline/candidate execution, metric comparison, and recorded conclusion—so reviewers can inspect what the system says and what its evidence actually supports.

It also includes a separate live integration with **NVIDIA Nemotron 3 Super through Nebius Token Factory**. That integration proposes a structured experiment; it does not execute the proposal or claim a measured speedup.

**Try it:** [Research workspace](https://axiom-frontend-demo.up.railway.app/#objective-workspace) · [Live Nemotron showcase](https://axiom-frontend-demo.up.railway.app/showcase) · [Source code](https://github.com/Flanxiyum001/Axiom)

> **Scope at a glance:** The hosted research workflow uses Echo reasoning and a constrained synthetic CPU workload. The live Nemotron showcase is a separate, bounded planning request. Neither demonstrates real GPU benchmarking, production inference optimization, TensorRT gains, or an executed Nemotron-driven experiment.

---

## The problem AXIOM explores

Optimization workflows can lose the connection between five things: the question, the hypothesis, the experiment, the evidence, and the conclusion. A fluent explanation is not the same thing as an experiment. An intervention label is not proof that an optimization was implemented. A metric printed by a script is not automatically a trustworthy measurement.

AXIOM brings those parts into one inspectable flow. Its contribution is a practical prototype for making research steps and evidence boundaries visible—not a claim that an autonomous agent has already discovered faster models.

## Start here: judge walkthrough

No account or API key is needed to try the public demo.

1. Open the [objective workspace](https://axiom-frontend-demo.up.railway.app/#objective-workspace).
2. Use the displayed latency-reduction objective, create it, and run **one** research iteration.
3. Inspect the hypothesis, plan, baseline/candidate outputs, provenance, evaluation, conclusion, and history.
4. Open the [live Nemotron showcase](https://axiom-frontend-demo.up.railway.app/showcase) and request a proposal.
5. Inspect its structured fields and evidence disclaimer. The result is a model-generated proposal, not an experiment result.
6. Compare the paths: the workspace demonstrates constrained synthetic execution; the showcase demonstrates live model-assisted planning.

The first showcase request may take several seconds. During its process-local cooldown, a repeated request may return a cached response rather than make a fresh provider call. The hosted research history is shared in process memory and resets when the backend restarts. Do not enter private or sensitive information.

## What the two paths demonstrate

| Path | Implemented behavior | Not demonstrated |
| --- | --- | --- |
| Research workspace | Create an objective, run a constrained research iteration, compare baseline/candidate metrics, inspect provenance and history. | Real model inference, GPU execution, independently verified speedups, or durable multi-user storage. |
| Nemotron showcase | Send a fixed, bounded request to NVIDIA Nemotron 3 Super via Nebius Token Factory and display a validated structured proposal. | Executing generated code, completing the proposed experiment, or measuring an optimization. |

## How the research loop works

1. **Objective intake** records the optimization question.
2. **Researcher** proposes a hypothesis and expected mechanism.
3. **Planner** turns it into a structured experiment specification.
4. **Execution** validates the specification and collects baseline/candidate output through the configured executor.
5. **Deterministic evaluation** compares metrics reported by experiment scripts and applies evidence checks.
6. **Analyst** records an interpretation and limitations.
7. **Persistence and inspection** retain research records locally for later review.

The evaluator is separate from the language-model reasoning stages, making comparison logic easier to inspect and test. However, it does not independently prove that an experiment implemented its claimed intervention or that reported values are truthful.

### Evidence boundaries are deliberate

- **Proposal ≠ execution.** The live Nemotron showcase does not execute generated code.
- **Reported metric ≠ independent ground truth.** The local engine reads metric JSON emitted by experiment code; scripts can report misleading values.
- **Intervention label ≠ proof of mechanism.** A name alone does not establish that an optimization was implemented.
- **Synthetic CPU timing ≠ ML inference latency.** The hosted executor times a built-in arithmetic workload; host load affects timings.
- **Reasoning provider ≠ execution backend.** Selecting Nemotron for reasoning does not turn a CPU workload into a GPU benchmark.

The known Echo intervention changes the amount of synthetic arithmetic. Unsupported or conflicting intervention claims receive an insufficient-evidence conclusion rather than an affirmative mechanism claim. This is a bounded prototype, not a general guarantee against deceptive experiment code.

## Architecture

```text
Browser
  -> Next.js frontend
       |-- Research dashboard
       |-- Live Nemotron proposal interface
       |     `-- Server-side bounded request to Nebius Token Factory
       `-- Allowlisted same-origin proxy for hosted research demo
               -> Private FastAPI backend
                    |-- Objective/run API
                    |-- Research-loop orchestration
                    |-- Researcher / Planner / Analyst
                    |-- Specification validation and execution
                    |-- Deterministic metric evaluation
                    `-- SQLite storage in local configuration
```

| Path | Responsibility |
| --- | --- |
| `frontend/app/page.jsx` | Research dashboard |
| `frontend/app/showcase/page.jsx` | Live-model proposal interface |
| `frontend/app/api/showcase/nemotron/` | Bounded server-side Token Factory request |
| `frontend/lib/judge-demo-proxy.mjs` | Allowlisted proxy for the fixed hosted demo |
| `backend/main.py` | FastAPI application |
| `backend/axiom/api/routes.py` | Objective, run, and history endpoints |
| `backend/axiom/services/research_loop.py` | Research-stage orchestration |
| `backend/axiom/execution/` | Validation, execution, and evaluation |
| `backend/axiom/memory/sqlite_repo.py` | Local research-record persistence |
| `backend/axiom/demo.py` | Fixed synthetic CPU demonstration |
| `backend/llm/nebius.py` | Optional Nebius reasoning provider |

The public demo uses fixed Echo reasoning and a built-in synthetic CPU task. The local executor uses Python subprocesses and is intended only for trusted local development—not hostile code. The optional Nebius backend reasoning path and experimental GPU adapter have not been verified end to end and are not part of the hosted research demo.

## Technology

- **Frontend:** Next.js, React
- **Backend:** Python, FastAPI, Pydantic
- **Local persistence:** SQLite
- **Model integration:** NVIDIA Nemotron 3 Super through Nebius Token Factory
- **Tests:** pytest, Node.js test runner, Playwright

## Reproducible real-ML inference experiment

AXIOM now includes an **optional local CPU benchmark** that uses scikit-learn's bundled handwritten-digits dataset and a real `StandardScaler + LogisticRegression` classifier. It compares per-row inference calls with one batched inference call using the same fitted model and test set. It checks prediction-label equivalence and reports repeated latency samples, median latency, throughput, accuracy, and environment details in JSON.

This is a separate, reproducible experiment—not the hosted synthetic demo, not a GPU benchmark, and not yet an execution path orchestrated by Nemotron.

```sh
python -m pip install -e '.[ml-benchmark]'
python -m experiments.real_inference_benchmark --repeats 10 --seed 42 --output artifacts/real-inference-benchmark.json
```

See [the benchmark protocol](docs/real-inference-benchmark.md) for the method and interpretation boundaries. Run it on the target machine and preserve its JSON report before quoting any measured result; a speedup is not guaranteed.

## Run locally

### Prerequisites

Python 3.11 or 3.12, Node.js 22, and npm.

### Install backend dependencies

From the repository root:

```sh
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

On Windows PowerShell, activate with `./.venv/Scripts/Activate.ps1` and run `python -m pip install -e ".[dev]"`.

### Start the offline backend

Linux / macOS:

```sh
export AXIOM_REASONING_PROVIDER=echo
export AXIOM_EXECUTOR_BACKEND=local
export PYTHON_DOTENV_DISABLED=1
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

PowerShell:

```powershell
$env:AXIOM_REASONING_PROVIDER = "echo"
$env:AXIOM_EXECUTOR_BACKEND = "local"
$env:PYTHON_DOTENV_DISABLED = "1"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd frontend
npm install --no-audit --no-fund
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The API docs are at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). The sample objective is `Reduce model inference latency by 20%`; it is an example research question, not a promise of a real-model speedup.

Local records default to `axiom.db` and `artifacts/`; override with `AXIOM_DB_PATH` and `AXIOM_ARTIFACT_ROOT`.

> **Security:** Run only trusted local experiments, preferably on a disposable, unprivileged system. AST validation and subprocess timeouts are not filesystem or network isolation. Never expose the unrestricted local executor API publicly.

## Optional: Nebius Token Factory

The backend defaults to Echo and does not require model credentials for an offline run. For optional live reasoning, configure the backend process environment or a local ignored `.env` file:

```dotenv
AXIOM_REASONING_PROVIDER=nebius
AXIOM_EXECUTOR_BACKEND=local
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
NEBIUS_MODEL=nvidia/nemotron-3-super-120b-a12b
NEBIUS_API_KEY=replace-with-your-own-token
```

Keep real keys out of source control and never place them in `NEXT_PUBLIC_*` variables. Live calls may incur charges. A provider-only check is available via `python -m scripts.smoke_nebius_reasoning --live`; it makes at most one external request and does not execute an experiment.

The hosted showcase uses a fixed request, response validation, bounded output, timeout, and process-local cooldown/cache. These controls constrain the demo but are not a global quota or a substitute for edge-level abuse protection.

## Tests and verification

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

The Playwright smoke suite exercises the research flow and provenance/history, and tests the showcase with a **mocked provider response**. It does not spend Token Factory credits. The constrained-demo configuration is available via `npm run test:smoke:demo`. Set `AXIOM_TEST_PYTHON` if the runner cannot locate the intended interpreter.

Tests verify behavior under their configured conditions. A mocked showcase test is not evidence of live provider availability, and passing tests do not turn synthetic timings into scientific benchmark results.

## Limitations and current status

- **Hosted demo remains synthetic:** its execution workload uses CPU arithmetic. A separate optional local scikit-learn classifier benchmark now measures real CPU ML inference; it is not a GPU benchmark and is not integrated into the hosted research loop.
- **No verified optimization claim:** no measured model-inference or TensorRT speedup is established.
- **No secure hostile-code sandbox:** local subprocess execution is for trusted development.
- **No independent metric attestation:** script-reported JSON values may be misleading.
- **Limited hosted persistence:** demo history is shared process memory and resets on backend restart.
- **Bounded live showcase:** Nemotron proposes an experiment; it does not run it. Cooldown/cache state is per process.
- **Unverified paths:** GPU execution and a fully live-provider research loop are not claimed as complete.

## FAQ

**Does AXIOM use NVIDIA Nemotron?** Yes. The live showcase uses NVIDIA Nemotron 3 Super through Nebius Token Factory to generate a structured proposal. The hosted research workspace uses Echo reasoning.

**Does AXIOM execute the Nemotron proposal?** No. The showcase does not execute generated code.

**Are the displayed latency numbers real model benchmarks?** No. The hosted research workflow uses synthetic CPU arithmetic.

**Can I configure another model or experiment?** The local architecture has configurable reasoning and execution components, but arbitrary local experiment scripts are trusted code. The experimental GPU path is not validated end to end.

**Does the public demo need my API key?** No. Provider credentials are configured server-side, not by the visitor.

**Is the hosted demo production-ready for multiple users?** It is a judge-facing prototype. History is process-local, and request limits are not global abuse protection.

## Further reading

- [Real-ML inference benchmark](docs/real-inference-benchmark.md) — reproducible CPU measurement protocol\n- [Pipeline assessment](docs/pipeline-audit.md) — measurement caveats and evaluator behavior
- [Experiment-layer guide](docs/experiment-layer.md) — execution and extension points
- [Judge demo notes](docs/judge-demo.md) — hosted demo boundaries
- [Hackathon submission draft](docs/hackathon-submission.md) — submission fields and remaining actions
- [Tool feedback worksheet](docs/tool-feedback.md) — prompts for genuine first-person feedback

## License

Apache License 2.0. See [LICENSE](LICENSE).
