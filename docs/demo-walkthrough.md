# AXIOM demo: 2 minutes 50 seconds

This is a recording script for the real dashboard, not a claim that a video already exists. Rehearse with both servers running, one iteration selected, browser text readable, and terminals hidden. Use a dedicated empty database/artifact directory. Never open `.env`, request headers, provider logs, or personal experiment outputs on camera. Record the reproducible Echo path unless a separately authorized live end-to-end rehearsal succeeds. The prior one-request Nemotron smoke check does not establish that the complete live loop works. Do not promise a numerical speedup before seeing the run. Leave ten seconds of buffer below the official three-minute limit; if the run takes longer, trim only idle waiting without altering or reordering measured results.

| Time | Exact action | Narration | Expected evidence |
| --- | --- | --- | --- |
| 0:00–0:18 | Open dashboard; show API connected and CURRENT PROVIDER. | “AI developers can lose the link between an optimization idea, experiment settings, and evidence. AXIOM keeps that chain visible.” | Connected indicator; actual provider name. |
| 0:18–0:35 | Enter `Reduce model inference latency by 20%`; click Create objective. | “This recording uses Echo offline. Separately, NVIDIA Nemotron 3 Super answered one live reasoning request through Nebius Token Factory.” | Active objective with latency metric and 20% target; provider still says echo. |
| 0:35–0:45 | Select 1 iteration; click Run research once. | “The researcher proposes a hypothesis; the planner makes an A/B plan and Python workload.” | Running state; no duplicate clicks. |
| 0:45–1:25 | Wait for actual completion; point to the hypothesis and plan. | “Here the workload is synthetic CPU arithmetic. Baseline and candidate run the same implementation in different experiment modes.” | Hypothesis, plan, and completed evaluation, or an honest execution error. |
| 1:25–1:48 | Scroll to provenance; show planned settings, specification parameters, and environment. | “Echo's candidate reduces arithmetic iterations. The `threads` and `precision` labels do not show real threading or quantization; provenance explains the script.” | Synthetic label; arithmetic iteration settings; experiment mode; intervention explanation. |
| 1:48–2:13 | Show the baseline/candidate table. | “These are this run's script outputs. A deterministic evaluator compares them. Any improvement applies only to this synthetic workload on this machine.” | Actual numbers and computed delta; speak only the values visible in this run. |
| 2:13–2:32 | Show Analyst conclusion and limitations. | “The analyst summarizes the result. AXIOM withholds a positive mechanism claim when the implementation is unknown or conflicts with the plan.” | Saved conclusion, confidence, and limitations. |
| 2:32–2:50 | Reload; reselect the objective if needed; end on saved provenance. | “The evidence is still here after refresh. This demonstrates a traceable offline research workflow, not a real-model speedup or GPU benchmark.” | Same hypothesis, measurements, provenance, and conclusion in history. |

## Recording checklist

- [ ] Start with a clean browser tab and dedicated demo storage; remove personal objectives and stale local results from the recording view.
- [ ] Confirm API connected and CURRENT PROVIDER says `echo` before pressing Record. If it differs, stop and fix the backend configuration; do not narrate Echo over a live provider.
- [ ] Hide terminals and notifications. Keep `.env`, keys, authorization headers, private logs, and personal files outside the capture area.
- [ ] Set readable browser zoom, window size, and audio level. Frame the actual dashboard, not slides or fabricated screenshots.
- [ ] Rehearse the narration against the on-screen actions; show hypothesis, plan/settings, baseline/candidate comparison, provenance, analyst conclusion, and saved history.
- [ ] Read observed numbers from the recorded run. If an execution error appears, re-record after fixing it; do not replace measurements or simulate success.
- [ ] Play the exported video from start to finish: verify legible text, intelligible narration, accurate provider/synthetic labels, no secret exposure, and duration below three minutes. Upload only after this review.

## Fallback

If live reasoning is unavailable, stop the live backend, set `AXIOM_REASONING_PROVIDER=echo`, `AXIOM_EXECUTOR_BACKEND=local`, and `PYTHON_DOTENV_DISABLED=1`, then restart the backend using the README command. Click Recheck and confirm CURRENT PROVIDER says echo. Use a new objective and follow the same script, explicitly saying the reasoning is offline. Never describe a saved Echo run as a live Nemotron result.

If execution fails during rehearsal, keep the error visible, inspect the backend locally, and rerun the browser smoke command before recording. If it fails during a presentation, show a previously recorded **labelled** Echo rehearsal from dedicated demo storage and state that it is saved evidence. Do not invent measurements or edit output to simulate a completed run.

## Ten-minute pre-demo checklist

- **10:00–8:00:** Confirm the intended branch/commit and final CI results. Check no personal files or keys are staged.
- **8:00–6:00:** Run `npm run test:smoke` with the virtual environment active; inspect the pass/fail result.
- **6:00–4:00:** Start a dedicated Echo backend and frontend using README commands. Confirm API connected, correct URL and provider. Close terminals containing private output.
- **4:00–2:00:** Create one objective, run one iteration, inspect actual baseline/candidate, provenance, conclusion, and refresh persistence.
- **2:00–0:00:** Reset to the opening view, rehearse the 2:50 narration, confirm the fallback is available and describe only observed results.
