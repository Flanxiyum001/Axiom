# AXIOM — 2:20 hackathon demo video script

**This is a recording script, not an existing video.** The judge demo combines two distinct capabilities: a constrained Echo/synthetic CPU research workflow and a separate live NVIDIA Nemotron 3 Super proposal via Nebius Token Factory. Do not describe the former as powered by live Nemotron or present the latter as an executed experiment.

| Time | Action on the real hosted application | Narration |
| --- | --- | --- |
| **0:00–0:15** | Open https://axiom-frontend-demo.up.railway.app/ and show the hero and API connected state. | “An optimization idea is not evidence. AXIOM keeps the journey from a question to a controlled experiment and interpretation visible.” |
| **0:15–0:35** | Go to the objective workspace; create the displayed objective, choose one iteration, run it. | “Our judge workspace runs a constrained, repeatable synthetic CPU demonstration with offline Echo reasoning.” |
| **0:35–1:05** | Scroll through hypothesis, plan, baseline/candidate comparison, provenance and conclusion. | “A deterministic evaluator compares two script outputs. These values are synthetic arithmetic workload results, not GPU benchmarks or real inference latency gains.” |
| **1:05–1:20** | Show history, then reload and verify the evidence remains while the backend is running. | “The record keeps the hypothesis, measurements and limitations together. Unsupported optimization claims do not become facts.” |
| **1:20–1:30** | Open https://axiom-frontend-demo.up.railway.app/showcase and frame the request button. | “Separately, AXIOM calls NVIDIA Nemotron 3 Super on Nebius Token Factory to propose a controlled experiment.” |
| **1:30–1:55** | Click generate once. Display the returned hypothesis, experiment, metric, safety boundary and limitation. If a valid cached response is returned, explicitly say it is cached. | “This response is structured live-model reasoning, not generated code execution. The proposal tells us what to measure, not what has been proven.” |
| **1:55–2:20** | Point to the evidence disclaimer; end on the AXIOM branding. | “AXIOM’s principle is simple: separate the hypothesis, the synthetic demonstration, and verified evidence. Next is independently instrumented real-model evaluation.” |

**The timings are targets, not guaranteed latency.** If the provider is slow or rate-limited, capture a truthful retry or use an accurately labeled cached response; do not edit footage to fabricate a fresh request. Leave around 40 seconds below the official three-minute maximum, but verify the finished file duration.

## Recording safety and QA

- [ ] Rehearse from a fresh browser. Use non-private demo data; ensure API connected / provider Echo in the research workspace.
- [ ] Use a single fixed objective and one run; metrics vary by machine. Narrate only numbers actually shown, and never guarantee the 20% target.
- [ ] Verify five nonblank structured model fields in the showcase; no generated code is executed.
- [ ] Hide terminal, private URLs, API keys, tokens, authorization headers, and personally identifiable information.
- [ ] Keep the text at a readable zoom, audio intelligible, and both URLs clearly demonstrated.
- [ ] Review the exported video end to end, including captions if used; make the English-language upload **public** on YouTube and confirm it is shorter than 3 minutes.
- [ ] Submit the actual video URL to Devpost. No video upload or Devpost submission happens automatically.

## If something fails during the demo

If the synthetic API is unavailable, check the frontend /api/health path and Railway deployments; do not present stored results as a new run. If Nemotron is unavailable, show the graceful error and state that the live proposal could not be verified at that moment. A prior verified provider response can be described as prior evidence, but never as a successful new invocation.

## Ten-minute pre-demo check

1. Confirm current main commit, safe demo mode, frontend/backend Railway deployment status, and final PR CI.
2. From a private/incognito browser, visit /, /#objective-workspace and /showcase. Verify route readability and no browser errors.
3. Create one objective, run one iteration, inspect provenance and refresh saved history; do not use private data.
4. Verify the showcase output or gracefully handled cooldown, without repeated paid provider calls.
5. Hide sensitive windows/notifications, then record the actual working app.

See [judge-demo.md](judge-demo.md), [hackathon-submission.md](hackathon-submission.md), and the official [rules](https://nebiusglobalaihackathon.devpost.com/rules).
