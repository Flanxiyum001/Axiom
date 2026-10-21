# AXIOM — Devpost submission draft

Copy and edit this draft for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/rules). The official deadline is **30 October 2026, 10:00 am PDT**. The rules require a working demo or test-build URL, a public repository, a public YouTube video under three minutes, a track choice, tool feedback, and an explanation of substantial changes if the project predates the submission period. This document is a draft, not a submitted entry.

## Submission fields

| Field | Draft value or next action |
| --- | --- |
| Project title | **AXIOM: Research loops with visible evidence** — ACTION REQUIRED: confirm title. |
| Tagline | Turn an optimization objective into a traceable experiment and saved assessment. ACTION REQUIRED: confirm wording. |
| Public repository URL | https://github.com/Flanxiyum001/Axiom |
| Working demo or test-build URL | **ACTION REQUIRED:** supply a judge-accessible URL and test it. A repository link and local setup instructions do not fill this field. |
| Public YouTube video URL | **ACTION REQUIRED:** record, upload publicly, and add the URL. No video is claimed here. |
| Selected track | **Recommended: Best Apps and Agents. ACTION REQUIRED:** select and confirm on Devpost. |
| Built With | Python, FastAPI, Pydantic, SQLite, Next.js, React, Nebius Token Factory, NVIDIA Nemotron 3 Super, pytest, Playwright. Confirm the final list matches the submitted build. |
| Team / entrant and eligibility | **ACTION REQUIRED:** confirm entrant, representative if applicable, ownership, and eligibility. |

## One-sentence description

AXIOM is an evidence-oriented research assistant that turns an optimization objective into a hypothesis, a controlled plan, an executed experiment, a measured comparison, and a saved explanation of what the result actually supports.

## Problem, audience, and value

AI developers and researchers must often move between an idea, experiment code, run settings, measurements, and a final interpretation. Tracking these by hand makes it easy to lose which implementation produced which numbers or to present a metric change as proof of an untested mechanism. AXIOM aims to keep that chain together for a researcher or ML engineer investigating optimization ideas.

The user enters a goal such as reducing latency. AXIOM creates a structured hypothesis and an A/B plan, runs a bounded workload, compares baseline and candidate metrics with a deterministic evaluator, and saves the hypothesis, specifications, runs, evaluation, and analyst conclusion. The dashboard exposes both fresh results and persisted history. Its useful distinction is **visible provenance and conservative interpretation**: it separates planned settings, executed code and environment, observed script output, and the claim that the evidence can support. Matching labels alone do not prove that a proposed optimization occurred.

## Technical implementation

The Next.js dashboard calls a FastAPI API. The API parses and persists objectives, then coordinates Researcher, Planner, and Analyst agents through the canonical research loop. The configured reasoning provider produces structured Pydantic output. Echo is the default for deterministic, credential-free demonstrations and automated tests. When explicitly configured, the existing Nebius provider sends reasoning requests to NVIDIA Nemotron 3 Super through the Nebius Token Factory OpenAI-compatible endpoint.

The Planner creates the experiment plan and Python specification. An AST validator checks the specification; the local executor runs it as a subprocess; a deterministic evaluator compares baseline and candidate outputs. SQLite and local artifacts retain the experiment record, and the dashboard displays provenance and saved history. The local executor has timeouts and limited controls but **is not a secure sandbox**; it must not be offered as an unauthenticated public code-execution service.

On 19 October 2026, the opt-in provider smoke command made **one real Token Factory request** with model `nvidia/nemotron-3-super-120b-a12b`. The response identified the same model and AXIOM validated its structured reply. This verifies the provider request and response handling only. It did not start the research loop, execute generated Python, submit a GPU job, or benchmark model inference. The key was not written to the repository or printed by the command. See the [README live verification record](../README.md#one-request-nemotron-smoke-test).

The complete dashboard demonstration uses Echo and a synthetic CPU arithmetic workload. Echo's candidate reduces arithmetic iterations. Its `batch_size`, `threads`, and `precision` names do not implement real batching, multithreading, or quantization. A measured reduction there is a result for that script on that machine, **not** a measured inference speedup, GPU throughput result, or independent attestation of a generated implementation. Live end-to-end Nemotron research behavior and Nebius AI Cloud GPU execution remain unverified.

## Track and potential impact

**Recommended track: Best Apps and Agents.** The official track describes a useful app or agent powered by Nemotron through Token Factory. AXIOM fits as a research workflow application with a visible dashboard and a verified Token Factory reasoning integration. The Coding and Agentic Engineering track is adjacent, but the current demo executes experiment code locally rather than running code in Token Factory. The selected track is a submission choice for the entrant to confirm. [Official track descriptions](https://nebiusglobalaihackathon.devpost.com/rules)

The practical value is a repeatable way to organize and inspect optimization experiments, especially when a team needs to distinguish an attractive hypothesis from measured evidence. The next technical step is a reviewed fixed-model inference benchmark: pin the model, dataset, configuration, and hardware; instrument baseline and candidate runs independently; verify output quality; and preserve raw samples. That future work could test actual optimization claims. No user adoption, production deployment, or real-model speedup has been demonstrated by this repository.

## Substantial work during the submission period

The repository's visible commit history begins on 17 September 2026, after the submission period opened on 26 August 2026. Within that period, the team built the research loop, experiment and evaluation layers, persistence, and Nebius integration. The October work added a usable Next.js dashboard, explicit experiment provenance and conservative conclusions, offline and browser regression coverage, and the opt-in live Nemotron smoke check ([PRs #33–#37](https://github.com/Flanxiyum001/Axiom/pulls?q=is%3Apr+is%3Amerged)). These changes materially improved the path from a technical pipeline to an inspectable user workflow and verified one external model request. **ACTION REQUIRED:** confirm whether any project existed before 26 August 2026 and, if so, describe the pre-existing baseline and the team's own significant updates in the final Devpost field.

## Judge testing instructions

1. **ACTION REQUIRED:** provide and verify the working demo or test-build URL, free judge access, and any needed test credentials in the submission form. Do not put a Nebius key in the repository, frontend, video, or public instructions. The current unauthenticated local executor is unsafe to expose publicly as-is.
2. For a local, credential-free walkthrough, use Python 3.11/3.12 and Node.js 22, follow the [README setup](../README.md#fresh-setup), start Echo plus the local executor, and open `http://localhost:3000`. This demonstrates the synthetic offline workflow; it is not a substitute for the required working-demo URL or a live Token Factory run.
3. Create `Reduce model inference latency by 20%`, choose one iteration, run it, then inspect the hypothesis, plan, baseline/candidate metrics, provenance, analyst conclusion, and reloaded history. Read the displayed measurements; do not expect fixed timing values.
4. The [opt-in provider smoke command](../README.md#one-request-nemotron-smoke-test) requires an authorized Nebius credential and may incur usage charges. Judges should not be expected to supply their own paid credential. **ACTION REQUIRED:** choose a safe way to demonstrate the Token Factory path to judges without exposing the host or a secret.

## Evidence and limitations to keep in the final entry

| Evidence | Verified claim | Claim it does not support |
| --- | --- | --- |
| One live Nemotron smoke request | AXIOM reached Token Factory with the configured model and validated one structured reply. | A complete live research run or optimization result. |
| Python, frontend, build, and browser checks | The Echo workflow and dashboard operate reproducibly offline with external-network test protection. | A production deployment or real Nemotron end-to-end workflow. |
| Synthetic CPU run metrics | The local script produced baseline/candidate values that the evaluator compared. | Real-model inference speedup, quantization, multithreading, or GPU performance. |
| Experimental Nebius GPU adapter | Code exists behind an explicit backend choice. | A verified GPU job, artifact retrieval, or cloud benchmark. |

Before submission, complete the [readiness checklist](hackathon-readiness.md), the [tool feedback](tool-feedback.md), and the [under-three-minute recording script](demo-walkthrough.md). Do not submit a placeholder URL or describe an unverified capability as demonstrated.
