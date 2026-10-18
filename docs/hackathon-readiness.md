# Hackathon submission readiness — 19 October 2026

This is a checklist against the [official Nebius x NVIDIA Global AI Hackathon rules](https://nebiusglobalaihackathon.devpost.com/rules), not a claim that an entry has been submitted. The listed deadline is **30 October 2026 at 10:00 am PDT** (22:30 IST). The official requirements include a working demo or test-build URL, a public code repository with a detectable open-source license and setup instructions, a public YouTube demonstration under three minutes, a track, tool feedback, and a substantial-update explanation when applicable. Check the form and rules again before submission.

There is no defensible numerical readiness score yet: a judge-accessible build, public video, and final Devpost fields are still missing. The target of 85% is a planning goal, not a measured result.

## Verified in code and CI

- [x] Canonical FastAPI research loop, Next.js dashboard, saved SQLite history, and visible provenance exist in the repository. [Architecture and evidence boundaries](../README.md#architecture-and-evidence-boundaries)
- [x] Echo and local execution are the default offline path. Automated tests disable dotenv, remove Nebius settings, and block external socket connections. [Test isolation](../tests/conftest.py)
- [x] The opt-in Token Factory smoke command uses the configured Nemotron model with at most one attempt and executes no generated code. [Command](../scripts/smoke_nebius_reasoning.py)
- [x] Python tests, frontend tests, production build, and Chromium browser smoke passed on the merged implementation PRs #35–#37. Recheck the final submission commit and its CI before entering Devpost.
- [x] README setup and the original Apache-2.0 license intent are documented. This branch replaces the abbreviated `LICENSE` with the official full Apache-2.0 text; **GitHub recognition on the final default branch still needs checking after merge**.
- [x] A ready-to-edit [submission draft](hackathon-submission.md), [recording script](demo-walkthrough.md), and [tool-feedback template](tool-feedback.md) are present on this branch.

## Verified manually

- [x] The GitHub repository is public and `main` contains merged PRs #35, #36, and #37 at this audit. The public URL is https://github.com/Flanxiyum001/Axiom.
- [x] On 19 October 2026, the provider-only smoke command made one real Nebius Token Factory request. It reported provider `nebius`, requested and response model `nvidia/nemotron-3-super-120b-a12b`, and `"validated": true`. The command did not print the credential. [README record](../README.md#one-request-nemotron-smoke-test)
- [x] The browser smoke exercises a complete **offline Echo** dashboard run and history reload. It does not prove a live research run.
- [x] At audit start, GitHub's public repository metadata returned `license: NOASSERTION` for the abbreviated license on `main`. The full license replacement in this branch addresses the file-level cause; badge recognition remains unverified until GitHub processes the merged default branch.

## Requires my action

- [ ] **ACTION REQUIRED — working demo or test build:** supply a URL that judges can access free of charge through the judging period, and verify it from a fresh browser. The current unauthenticated local API and executor are not safe to publish as-is. A repository link alone is not the separate working-demo field. Plan safe Token Factory access without sharing a key or requiring judges to pay.
- [ ] **ACTION REQUIRED — video:** rehearse the [2:50 walkthrough](demo-walkthrough.md), record the real dashboard, review it for legibility and secret safety, upload an English-language video publicly to YouTube, and place its URL in Devpost. The official limit is under three minutes; no video URL exists in this repository.
- [ ] **ACTION REQUIRED — submission content:** confirm project title/tagline, select the recommended Best Apps and Agents track or choose a better-supported official track, complete the [tool feedback](tool-feedback.md), explain substantial hackathon-period work, and enter the final description and Built With list.
- [ ] **ACTION REQUIRED — entrant and repository checks:** confirm team representative, eligibility, ownership, third-party material rights, and whether a pre-period version existed. After this PR merges, verify that GitHub detects Apache-2.0 at the top of the public repository, that final-commit CI passes, and that the README instructions work on a clean machine.
- [ ] **ACTION REQUIRED — Devpost:** review the live official form and rules, add working links and any judge access instructions, and submit before the deadline. This repository audit does not submit an entry.
- [ ] **ACTION REQUIRED — credential hygiene:** rotate any credential previously shared outside the team's intended secret store. Keep credentials out of the repository, frontend environment, recording, and submission text.

## Blocked or not implemented

- [ ] No judge-accessible hosted application or test-build URL has been verified. A public deployment of the current local executor would be unsafe without isolation, authentication, and resource controls. [Pipeline audit](pipeline-audit.md)
- [ ] No public YouTube video or submitted Devpost entry is evidenced here.
- [ ] Full live Nemotron research-loop behavior, independently measured real-model inference improvements, quantization, true multithreading, Nebius GPU jobs, and GPU performance remain unverified. The Echo demo measures synthetic CPU arithmetic only.

## Local audit command

Run `python -m scripts.check_hackathon_readiness` from the repository root. The script checks only explicit local artifacts and counts unresolved `ACTION REQUIRED` markers. A zero exit means the local audit ran and its expected files exist; it **does not** mean the submission is ready. It never opens URLs, reads credentials, calls Nebius, verifies CI, or decides whether a deployment is safe. The human and external checks above remain necessary.

## This branch's local verification

- Python suite: `345 passed` with `python -m pytest tests/ -q`.
- Frontend unit tests: `9 passed` with `npm test`; `npm run build` completed successfully.
- Chromium dashboard smoke: `3 passed` with `npm run test:smoke`, using the offline Echo configuration.
- Local artifact audit: all explicitly listed files present, with unresolved owner actions; it reported `Submission readiness: NOT VERIFIED`.
- Relative document links and `git diff --check`: passed. Final PR CI and external submission materials remain separate checks.
