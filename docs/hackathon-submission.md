# AXIOM — hackathon submission draft (updated 28 October 2026)

**Submission status: DRAFT — not submitted.** Enter the final details in Devpost; do not interpret a working hosted URL or green CI as proof of submission.

## Copy-ready fields

| Field | Submission value |
| --- | --- |
| Project name | **AXIOM — Research loops with visible evidence** (confirm final name) |
| Tagline | From optimization questions to traceable experiments, with honest evidence boundaries |
| Public GitHub | https://github.com/Flanxiyum001/Axiom |
| Hosted demo | https://axiom-frontend-demo.up.railway.app/ |
| Objective workspace | https://axiom-frontend-demo.up.railway.app/#objective-workspace |
| Live model showcase | https://axiom-frontend-demo.up.railway.app/showcase |
| Recommended track | **Best Apps and Agents** — entrant must select the track |
| Built with | Next.js, React, FastAPI, Python, SQLite, Pydantic, Nebius Token Factory, NVIDIA Nemotron 3 Super, pytest, Playwright |
| Public YouTube video | **ACTION REQUIRED:** upload an English-language demo shorter than three minutes and enter its URL |
| Entrant/team | **ACTION REQUIRED:** confirm eligible entrant and, if a team, authorized representative |

### One-sentence pitch

AXIOM helps ML developers turn optimization questions into structured experiments, inspect synthetic measurement evidence, and distinguish verified observations from AI-generated proposals.

### Project description (approximately 130 words)

Machine-learning experimentation often loses the connection between a hypothesis, its implementation, the resulting measurements, and what those measurements truly establish. AXIOM is an evidence-oriented research workspace that keeps those steps visible. In the hosted research lab, users create a latency-reduction objective, run a constrained synthetic CPU experiment, compare baseline and candidate metrics, and inspect the saved hypothesis, plan, provenance, evaluation, and analyst conclusion. Separately, the live model showcase requests a structured experiment proposal from NVIDIA Nemotron 3 Super through Nebius Token Factory, with bounded server-side calls, validation, caching and clear error states. AXIOM distinguishes a model-generated hypothesis from executed work and explicitly labels its synthetic measurements. It does not claim real GPU benchmarking, TensorRT optimization, verified inference speedups, or a completed autonomous Nemotron-driven experiment. Its contribution is a practical interface for inspecting the chain from question to evidence.

## Architecture and what actually runs

1. **Public Next.js frontend:** research dashboard and separate model showcase. The synthetic judge API is a narrow same-origin proxy.
2. **Private FastAPI backend:** fixed Echo demo mode, an allowlisted synthetic CPU executor, deterministic evaluation, and in-memory demo history. The ordinary local executor is **not** a secure sandbox and is not exposed for arbitrary public code execution.
3. **Live Nebius integration:** the Next.js server-side showcase route sends a fixed, bounded request to Token Factory using the NVIDIA Nemotron 3 Super model. The server validates response fields and model identity; no generated code is run through this showcase. Request cooldown and cached responses are per-process, not a global quota or security boundary.
4. **Evidence boundary:** the hosted research workflow is **Echo + synthetic CPU execution**. The hosted model showcase is **live LLM-generated planning**, not a measured experiment. Experimental GPU adapter code is not verified end-to-end.

On 19 October, a separate authorized provider-only smoke test verified one response from the expected Nemotron model. The user-provided deployment record and Railway HTTP logs on 28 October show successful hosted demo routing and objective create/run/history requests. The model showcase has previously returned a structured response, but this submission should not claim a measured GPU result or a complete live-provider research loop.

## What is distinctive and useful

AXIOM keeps objective, plan, implementation indicators, script metrics, evaluation, analyst interpretation, and history in one inspectable flow. It withholds affirmative mechanism claims when a proposed intervention is unsupported. This directly addresses a common problem in research tooling: attractive optimization labels that outpace the evidence.

## How judges can test it

1. Open the **hosted demo** URL above; use a desktop browser if possible. No Nebius key or paid account is required for the visitor.
2. In the objective workspace, use the displayed fixed latency-reduction objective, create it, and run **one** research iteration. Inspect baseline/candidate script metrics, synthetic provenance, conclusion, and history. A duplicate run or additional iterations may be blocked by design.
3. Open the **live model showcase**. Request a proposal; inspect its five structured fields and explicit evidence disclaimer. The first request may take several seconds. A repeat call may return a cached result during the cooldown; rate limits/provider failures may produce an error. Never claim that a cached output is a fresh model call.
4. Avoid interpreting synthetic arithmetic timings as real ML inference improvements. Do not enter private information into the shared demo.

Keep the hosted demo freely accessible **through the hackathon judging period**; see [judge-demo.md](judge-demo.md) for the narrow proxy and deployment boundaries.

## Tool feedback — entrant must personalize

**Confirmed use:** NVIDIA Nemotron 3 Super via Nebius Token Factory for structured experimental-reasoning proposals. Separately, the Echo demo demonstrates the execution/evidence interface. **Not confirmed:** production Nebius AI Cloud GPU jobs, inference benchmarking or verified optimizations.

**ACTION REQUIRED:** supply genuine first-person feedback on Token Factory/model onboarding, what helped, friction encountered, changes requested, and whether you would use the tools again. The editable [tool-feedback worksheet](tool-feedback.md) provides prompts; do not invent experiences.

## Substantial hackathon-period work

Repository history contains September–October 2026 development of the research loop, objective flow, structured reasoning, experiment evaluation, persistence, dashboard, safety boundaries, provider smoke verification and judge-facing hosted demo. **ACTION REQUIRED:** confirm whether any version existed before the submission period beginning 26 August 2026; if yes, accurately identify pre-existing work and the substantial new changes.

## Demo video

Use [demo-walkthrough.md](demo-walkthrough.md) for an approximately 2-minute-20-second recording that shows **both** the research workspace and the live showcase, clearly narrating the difference. Record only actual functioning footage, hide secrets, and upload a **public** YouTube video under three minutes. No video has been uploaded by this document.

## Final submit checklist

- [ ] Verify the hosted demo from a fresh browser, including create/run/history and the showcase.
- [ ] Check the final GitHub commit and passing Python, frontend and browser CI; inspect Apache-2.0 recognition on the public repository page.
- [ ] Upload and review public YouTube demo, shorter than three minutes.
- [ ] Fill in final title, description, track, Built With, real tool feedback and entrant eligibility.
- [ ] Confirm the old-project/substantial-update declaration, license/asset rights, and any judge testing instructions.
- [ ] Submit on Devpost **before Friday 30 October 2026, 10:00 am PDT (10:30 pm IST)**.
- [ ] Keep the testable build free and available through the judging window.

Official source: https://nebiusglobalaihackathon.devpost.com/rules. No action in this document submits the project or certifies eligibility.
