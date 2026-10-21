# Constrained judge demo: deployment preparation

This mode is an opt-in test build for a **fixed synthetic CPU demonstration**. It is not deployed by this repository. The recorded measurements come from arithmetic loops actually timed on the demo host; values vary with machine load. They do not measure Nemotron inference, GPU performance, quantization, or multithreading. Echo supplies deterministic hypothesis/plan/analysis structure. No Token Factory request is made by the demo.

## Boundary and audit

The ordinary `/objectives/{id}/run` route reaches `LocalExecutor`, which executes spec Python in a subprocess. Its AST validator and resource limits are not a secure sandbox. Do not publish the ordinary backend. The frontend's CORS setting does not authenticate an API.

With `AXIOM_DEMO_MODE=1`, startup requires Echo, the local backend selection, `AXIOM_DB_PATH=:memory:`, and no Nebius or storage credentials. The service constructs `FixedSyntheticDemoExecutor` instead of `LocalExecutor` or the GPU adapter. Its only work is a compiled-in arithmetic loop with fixed baseline/candidate counts; it checks the known spec marker and ignores executable spec code. Artifact access also fails closed. There is no fallback to a configured live provider or unrestricted executor. The existing trusted local workflow remains available with demo mode off.

The public API accepts only `Reduce model inference latency by 20%`, one iteration, and one run per objective. One API process allows one active run, at most 100 objectives, 6 mutations per client and 30 total mutations per minute, and 2 KiB POST bodies. `/research` is disabled; API docs are hidden. These are process-local limits, not a substitute for ingress controls. History is shared among visitors and vanishes when the process restarts; do not enter private information.

## Environment and launch shape

Use [.env.judge-demo.example](../.env.judge-demo.example) for backend variables and [frontend/.env.judge-demo.example](../frontend/.env.judge-demo.example) for browser build variables. Only an API URL belongs in `NEXT_PUBLIC_AXIOM_API_URL`. Set `NEXT_PUBLIC_AXIOM_DEMO_MODE=1`; the browser refuses a backend whose `/health` does not report `demo_mode: true`. The backend guard is independent of this browser check.

Before exposing a URL, the owner must choose a host and place the two processes behind HTTPS ingress. Run the backend as an unprivileged, disposable process/container with **one worker**, a read-only application filesystem where practical, no cloud credentials, no access to trusted local files or databases, and outbound network blocked. Keep its separate in-memory database and any transient files away from trusted development data. Set `PYTHON_DOTENV_DISABLED=1` in the backend process environment **before** Python starts. Do not mount a developer `.env`. Start Uvicorn without `--reload` or extra workers, and set `AXIOM_CORS_ORIGINS` to the exact HTTPS frontend origin. Set the frontend's `NEXT_PUBLIC_AXIOM_API_URL` to the actual constrained backend origin at build time. No host, provider, or URL is selected here.

At the trusted HTTPS ingress, apply request rate and body-size limits to **all** routes, connection and request timeouts, and a cap on concurrent connections. The built-in limits cover mutation routes in one process; they do not cover GET flooding, multiple workers/replicas, or a hostile network. The owner should verify the platform's own resource and network policies before giving judges the URL.

## Credential-free verification before sharing

1. Inspect the backend environment and confirm the safe values above. Do not print environment dumps or secrets. Confirm it has no Nebius credentials and no mounted trusted data.
2. Check `/health`: it must report `provider: "echo"`, `demo_mode: true`, and `workload: "fixed_synthetic_cpu"`. If it does not, stop the rollout.
3. From a fresh browser, create the displayed fixed objective, run one iteration, inspect the hypothesis, plan, actual baseline/candidate `latency_ms` samples, provenance, conclusion, and reloaded history. Do not expect a particular timing or a guaranteed target result.
4. Confirm another objective, a second run of the same objective, an iteration count above one, `/research`, and an oversized POST are rejected. Confirm the browser shows the synthetic CPU label and does not reveal a credential.
5. Independently check the public URL, TLS, ingress limits, and logs from outside the hosting account. This repository's tests cannot establish those properties.

To shut down after judging, remove the public ingress route, stop both processes, delete their disposable logs according to the host policy, and remove the demo environment and any temporary hosting credentials. The in-memory history disappears when the backend stops. No Nebius API key is needed or permitted in this demo process.

## Remaining submission limit

The safe test build shows AXIOM's objective → hypothesis → controlled synthetic measurement → deterministic comparison → provenance → conclusion workflow. It does **not** supply a judge-accessible URL by itself, nor does it demonstrate a live Nemotron research run. The earlier provider-only Token Factory smoke is separate evidence. The owner must authorize and verify hosting, then decide how to present both pieces of evidence honestly in the submission.
