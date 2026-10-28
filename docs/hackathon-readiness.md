# AXIOM — hackathon readiness checklist (28 October 2026)

**Release decision:** the hosted demo is deployed and the core synthetic create/run/history path has successful Railway HTTP logs. A live Nemotron proposal route exists separately and has previously returned structured output. Final PR CI, visual browser checks, entrant feedback, a public YouTube video, and Devpost submission still need completion. **Not yet a submitted entry.**

Official deadline: **Friday 30 October 2026 at 10:00 am PDT = 10:30 pm IST**. Judges must have a working, free-to-use demo through the judging period ending 15 December 2026. Source: https://nebiusglobalaihackathon.devpost.com/rules

## What the repository and deployment actually show

- [x] Next.js frontend and private FastAPI backend deployed successfully to Railway on 28 October. Both services report SUCCESS; the backend has no public domain.
- [x] Same-origin /api health and objective endpoints have 200/201 HTTP log evidence for health, create, run, and history.
- [x] Homepage and /showcase page have successful HTTP access logs. The /showcase server route sends a fixed, bounded Nebius Token Factory request. One previous live model reply and its structured parsing were recorded; do not conflate this with synthetic execution.
- [x] Python backend tests, frontend tests and browser-smoke workflows exist in GitHub Actions. Their results must be checked at the final submission commit, not inferred from older green runs.
- [x] README contains environment/setup guidance; an Apache-2.0 license file exists. GitHub's visible license detection still requires an independent final check.
- [x] Copy-ready submission draft and concise two-path video script exist in the docs.

## Judge-facing links

- Hosted research lab: https://axiom-frontend-demo.up.railway.app/#objective-workspace
- Live structured Nemotron proposal: https://axiom-frontend-demo.up.railway.app/showcase
- Source code: https://github.com/Flanxiyum001/Axiom

The research lab uses **Echo + a fixed synthetic CPU demonstration**; the live model showcase is a **proposal**, not real inference benchmarking. No TensorRT, GPU performance, true multithreading, real model speedup or complete end-to-end live Nemotron research loop is verified.

## Release gates — do before the submission

- [ ] Verify final-head Python 3.11 + 3.12 CI, frontend unit/build, and Chromium browser smoke. Review pending UI PR #44 and the follow-up showcase-readiness PR separately. Do not merge while checks are failing or running.
- [ ] Open the public demo from a fresh browser; verify readable layout on desktop/mobile, objective create/run/history after refresh, and a showcase request or clearly labeled cached response. Observe graceful failures.
- [ ] Confirm the server-side Nebius key is **not** in any NEXT_PUBLIC value, logs, repository, video, or browser bundle. Avoid logging credentials. Do not make needless paid requests.
- [ ] Confirm GitHub shows the open-source license in its visible metadata, and the README setup matches the final branch.
- [ ] Record, review and upload a **public English-language YouTube video under three minutes**, showing actual working app footage. See [demo-walkthrough.md](demo-walkthrough.md).
- [ ] Confirm final name, tagline, Best Apps and Agents (or other correct track), Built With, public video URL, team/entrant eligibility, rights, and pre-existing-project explanation.
- [ ] Supply personal, factual tool feedback via [tool-feedback.md](tool-feedback.md); do not invent Nebius GPU use.
- [ ] Complete the required Devpost fields and submit **before 10:30 pm IST on 30 October**; verify the submission is actually entered.
- [ ] Keep the demo available for judges through 15 December 2026; plan a safe shutdown only after the judging window.

## Release constraints

Do **not** replace the fixed synthetic judge executor with the ordinary local code executor on the public backend; its AST checks are not a host-level sandbox. Do **not** change Railway production infrastructure merely to pass superficial checks. The demo stores shared, non-private history in memory; a process restart clears it. Provider request caching and cooldown are per-process only. Use the final GitHub PR checks and real browser observations as separate evidence.

Submission draft: [hackathon-submission.md](hackathon-submission.md). Safeguards: [judge-demo.md](judge-demo.md). Historical audit (19 October): [release-audit.md](release-audit.md).
