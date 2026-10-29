# Constrained judge demo: Railway deployment guide

This is an opt-in **fixed synthetic CPU demonstration**. Echo supplies the hypothesis, plan, and analysis structure. The demo times a compiled-in arithmetic loop on the demo host; values vary with host load. It does not measure Nemotron inference, GPU performance, quantization, or multithreading. The fixed research-workspace flow makes no Token Factory request. The separate public `/showcase` page makes a bounded, server-side Nebius Token Factory request; it generates a proposal only and does not invoke the private demo executor.

## Deployment shape: public frontend, private backend

Deploy two services from this repository into the **same Railway project and environment**:

- **Frontend**: root directory `/frontend`, Next.js service with the only public Railway domain.
- **Backend**: repository root `/`, FastAPI service listening on port `8000`. Do **not** generate a public domain for it. Set its private networking endpoint to `axiom-backend`, so the internal address is `http://axiom-backend.railway.internal:8000`.

The browser must never call the backend's public address. The browser uses the same-origin path `/api`; the Next.js route handler forwards only a short allowlist of health/objective/history/run calls to the private backend. It rejects unsupported paths, enforces request-size and per-process rate limits, uses a timeout, disables redirects, limits response size, and returns sanitized gateway errors. Do not add a general-purpose URL proxy.

### Frontend Railway variables

Set these on the frontend service. `NEXT_PUBLIC_*` values are baked into the browser build; the internal backend URL is server-side only.

```dotenv
NEXT_PUBLIC_AXIOM_DEMO_MODE=1
NEXT_PUBLIC_AXIOM_API_URL=/api
AXIOM_BACKEND_INTERNAL_URL=http://axiom-backend.railway.internal:8000
```

### Separate live showcase (Next.js server only)

The public frontend also exposes `/showcase`, which makes a fixed, rate-limited server-side request to Nebius Token Factory. Only the Next.js server runtime should have its `NEBIUS_API_KEY`; never put it in a `NEXT_PUBLIC_*` variable. This feature is **not** routed through `/api/[...path]` or the private fixed synthetic executor, and it does not execute the model's proposed code. It should be demonstrated as a proposal, not a benchmark.

### Backend Railway variables

Set these only on the backend service:

```dotenv
PYTHON_DOTENV_DISABLED=1
AXIOM_DEMO_MODE=1
AXIOM_REASONING_PROVIDER=echo
AXIOM_EXECUTOR_BACKEND=local
AXIOM_DB_PATH=:memory:
AXIOM_MAX_ITERATIONS=1
AXIOM_RUN_TIMEOUT_SECONDS=10
PORT=8000
AXIOM_CORS_ORIGINS=
```

Do not add Nebius, storage, cloud, or other provider credentials to the **private fixed-demo backend**. For the **separate live showcase only**, the frontend's Next.js server runtime may use `NEBIUS_API_KEY` and `AXIOM_NEBIUS_SHOWCASE_ENABLED=1` as server-only environment variables. Neither may be named `NEXT_PUBLIC_*`, sent to the browser, or printed in logs. Do not mount the developer's local `.env`. Run the backend with one worker and no auto-reload:

```sh
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Build the frontend from `/frontend` with `npm install --no-audit --no-fund`, `npm run build`, then start with `npm run start -- --hostname 0.0.0.0 --port ${PORT}`. Use one replica for each service during judging. Keep the backend's internal address private and verify that the backend service has **no public domain**. This also means CORS is not the security boundary: the browser speaks only to the public frontend.

## Execution and network boundaries

The ordinary local workflow can execute generated spec Python through `LocalExecutor`; its AST checks and subprocess limits are **not a secure sandbox**. Never expose the ordinary backend publicly.

With `AXIOM_DEMO_MODE=1`, startup requires Echo, local executor selection, an in-memory DB, and no Nebius or storage credentials. The app constructs `FixedSyntheticDemoExecutor`, which validates a fixed spec marker and ignores executable spec code. It runs only a built-in arithmetic loop. Artifact access is disabled. `/research`, API documentation, arbitrary objectives, multiple iterations, and duplicate runs are disabled.

**Railway caveat:** Railway's current networking documentation does not provide a general deny-all outbound firewall rule for application services. The architecture here therefore does not claim OS-level egress isolation. Its intended **synthetic-workspace API path** has no generated-code execution, user-controlled URL fetch, live provider request, or cloud credentials; the backend remains private. The separate Next.js showcase route does make an explicitly bounded live provider request using a server-side credential and is not forwarded to this backend. If a host-level outbound-deny policy is required by your threat model, use a host/network setup that can enforce it before sharing the demo. Do not repurpose this configuration for arbitrary code execution or untrusted workloads.

The proxy allows only the intended demo API routes, rejects query-string routing, limits request bodies to 2 KiB and responses to 512 KiB, applies process-local request/mutation caps, and times out upstream calls. The backend itself caps objective creation, mutation volume, and concurrent runs. These application limits are not a substitute for upstream protection against a large HTTP flood. Configure any ingress/edge limits available on your chosen plan and keep the demo temporary. Do not enter private data; saved demo history is shared among visitors and disappears when the in-memory backend restarts.

## Backend image configuration for Railway

The repository-root [Dockerfile](../Dockerfile) is the deterministic backend image for the judge demo. It uses Python 3.12, installs the project dependencies into the same image that runs the API, disables dotenv loading, and starts Uvicorn with one worker. On Railway, configure the backend service to use the root `Dockerfile` and health check `/health`; clear the custom Railpack build-command override so the Dockerfile controls installation. Do not select this Dockerfile for the frontend service, which uses `/frontend` as its root directory and Railpack's Next.js build.

Keep the backend on its private Railway address and do not generate a public domain for it. If the deployment logs do not show the API starting and the health check succeeding, do not expose the frontend URL to judges.

## Verification before sharing the frontend URL

1. Check the Railway backend settings: one replica/worker, port 8000, no public domain, no credentials, no persistent volume, and `PYTHON_DOTENV_DISABLED=1` set before Python starts.
2. Check backend private connectivity from the frontend service. The frontend variable must point to `http://axiom-backend.railway.internal:8000`; do not swap it for a public backend URL.
3. Open the **frontend's HTTPS URL** in a fresh browser. `/api/health` must report `provider: "echo"`, `demo_mode: true`, and `workload: "fixed_synthetic_cpu"`.
4. Create the displayed objective, run one iteration, inspect hypothesis, plan, actual baseline/candidate timings, provenance, conclusion, and history after refresh. Do not expect fixed timings or guaranteed target attainment.
5. Confirm unsupported proxy paths such as `/api/research` are rejected, an oversized POST is rejected, a second run is rejected, and request limits return a safe error. Check browser devtools: API calls must go to the frontend's same-origin `/api` path, never a public backend URL.
6. From outside Railway, verify HTTPS and the public frontend URL. In Railway, independently verify the backend domain list is empty and the frontend backend variable is the private address. Check sanitized logs; never dump environment variables.
7. If any of these checks fail, remove/disable the frontend's public domain and stop the rollout until fixed.

## Shutdown after judging

Remove the frontend's public domain or ingress route, stop the frontend and backend services, remove temporary variables and hosting resources, and handle logs according to the host's retention policy. In-memory experiment history disappears when the backend process stops. The fixed synthetic research flow needs no Nebius key; the separate live showcase uses a server-side credential that must be removed when that showcase is shut down.

## Remaining limitation

This provides a constrained, runnable UI workflow around a synthetic CPU measurement. It does not verify the full live Nemotron research loop, model-inference speedup, GPU execution, or GPU performance. The live `/showcase` is a separate server-side Nemotron proposal experience. Neither it nor the earlier provider-only smoke test proves a complete Nemotron-driven research experiment.
