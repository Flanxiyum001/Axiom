# AXIOM demo: 2 minutes 40 seconds

Rehearse with both servers already running, one iteration selected, browser zoom readable, and terminals hidden. Use a dedicated empty database/artifact directory. Never open `.env`, request headers, provider logs, or personal experiment outputs on camera. Use Echo unless a separately authorized live rehearsal has succeeded. Do not promise a numerical speedup before seeing the run.

| Time | Exact action | Narration | Expected evidence |
| --- | --- | --- | --- |
| 0:00–0:15 | Open dashboard; show API connected and CURRENT PROVIDER. | “AXIOM turns an optimization question into an experiment with saved evidence. This session uses Echo for offline reasoning.” For an authorized live session, say “Nebius/Nemotron supplies the reasoning.” | Connected indicator; actual provider name. |
| 0:15–0:30 | Enter `Reduce model inference latency by 20%`; click Create objective. | “This is the research goal, not a claim that a model has improved.” | Active objective with latency metric and 20% target. |
| 0:30–0:40 | Select 1 iteration; click Run research once. | “The researcher proposes a hypothesis; the planner produces an A/B plan and Python workload.” | Running state; no duplicate clicks. |
| 0:40–1:00 | Wait for actual completion; point to hypothesis. | “In this demonstration, the workload is synthetic CPU arithmetic. Baseline and candidate use the same implementation, with different experiment modes.” | Hypothesis and completed evaluation, or an honest execution error. |
| 1:00–1:25 | Scroll to benchmark provenance; show planned baseline/candidate settings, parameters and environment. | “Echo models the intervention by reducing arithmetic loop iterations. These labels do not demonstrate real batching, threading or quantization. The provenance records what the script actually represents.” | Synthetic label; arithmetic iteration settings; mode candidate; intervention explanation. |
| 1:25–1:50 | Show Baseline vs candidate table. | “These values came from the executed script's output. The evaluator computes this comparison deterministically. Any improvement applies only to this synthetic workload on this machine.” | Actual baseline/candidate numbers and computed delta; read the observed values only. |
| 1:50–2:10 | Show Analyst conclusion and limitations. | “The analyst explains the measured result. Unknown or conflicting generated interventions receive an insufficient-evidence conclusion. A generated explanation is not independent measurement verification.” | Saved conclusion, confidence and limitations. |
| 2:10–2:25 | Reload page; reselect the objective if needed. | “The hypothesis, implementation, runs and conclusion remain available in saved history.” | Same hypothesis, provenance and evaluation after reload. |
| 2:25–2:40 | End on provenance. | “This demonstrates a traceable research workflow. It does not establish a real-model latency gain or a GPU benchmark. The next benchmark needs a fixed model, dataset, controlled treatment and independently instrumented measurements.” | Explicit synthetic wording remains visible. |

## Fallback

If live reasoning is unavailable, stop the live backend, set `AXIOM_REASONING_PROVIDER=echo`, `AXIOM_EXECUTOR_BACKEND=local`, and `PYTHON_DOTENV_DISABLED=1`, then restart the backend using the README command. Click Recheck and confirm CURRENT PROVIDER says echo. Use a new objective and follow the same script, explicitly saying the reasoning is offline. Never describe a saved Echo run as a live Nemotron result.

If execution fails during rehearsal, keep the error visible, inspect the backend locally, and rerun the browser smoke command before recording. If it fails during a presentation, show a previously recorded **labelled** Echo rehearsal from dedicated demo storage and state that it is saved evidence. Do not invent measurements or edit output to simulate a completed run.

## Ten-minute pre-demo checklist

- **10:00–8:00:** Confirm the intended branch/commit and final CI results. Check no personal files or keys are staged.
- **8:00–6:00:** Run `npm run test:smoke` with the virtual environment active; inspect the pass/fail result.
- **6:00–4:00:** Start a dedicated Echo backend and frontend using README commands. Confirm API connected, correct URL and provider. Close terminals containing private output.
- **4:00–2:00:** Create one objective, run one iteration, inspect actual baseline/candidate, provenance, conclusion, and refresh persistence.
- **2:00–0:00:** Reset to the opening view, rehearse the 2:40 narration, confirm the fallback is available and describe only observed results.
