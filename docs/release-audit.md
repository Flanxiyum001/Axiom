# Release audit — 19 October 2026

## Repository and review scope

PR [#34](https://github.com/Flanxiyum001/Axiom/pull/34) was already merged at `5d4b90cf4ec51e039b6e9eac0803e4312cd844af` when this audit started. Its head was `b039b79487970b0db9f0eb298d0aecd0735582d8`. GitHub reported final success for Python 3.11, Python 3.12, Next.js production build (including frontend tests), and CodeRabbit. No PR was open at initial inspection; #33, #32 and #31 were also merged. This work belongs on `fix/sprint-release-readiness`, based on merged main, as authorized after discovering that #34 was merged. No merge or direct main modification is part of this work.

Untracked user scripts, `.claude/`, artifacts, the local database and package lockfile are excluded from the commit. Dependency installation updated the local untracked package lockfile; it remains available locally. Next.js generated `frontend/AGENTS.md` during the smoke test; this framework guidance is included with the change. The detached `.sprint-baseline` worktree is retained for audit reproducibility.

## Verification evidence

- Unchanged merged main: **328 passed**, one dependency deprecation warning, Python 3.14 on Windows, 101.05 seconds, with explicit safe CI-style configuration and dotenv disabled.
- Follow-up full suite before the final extra UTF-8 regression: **338 passed**, one dependency deprecation warning, twice (99.17 and 100.33 seconds), Python 3.14 on Windows.
- The four historically reported tests: **4 passed** together; each also passed in a separate pytest invocation.
- Focused intervention/UTF-8 regression module: **7 passed**.
- Final complete local suite including UTF-8 regression: **339 passed**, one dependency deprecation warning, 101.47 seconds.
- Frontend provenance: **9 passed**, no failures or skipped tests.
- Frontend production build: successful static production build.
- Chromium smoke: **1 passed** twice (12.8 and 9.0 seconds), including actual API execution and refresh persistence.

The final full-suite count and supported Python 3.11/3.12 results are recorded in the follow-up PR's check results. Local Python 3.11/3.12 are unavailable; Python 3.14 evidence is supplementary. The original backend/frontend jobs remain intact; a separate browser-smoke workflow runs on Ubuntu/Python 3.12/Node 22 and retains diagnostics on failure. Final release approval requires all checks on the final PR head to complete successfully.

## Historical failure diagnosis

| Reported test | Verified failure mechanism / limit of diagnosis | Minimal hardening and regression |
| --- | --- | --- |
| `test_research_loop_reaches_target` | `Settings()` reads process provider/executor configuration; importing the app can load personal dotenv configuration. The historical failure did not reproduce under safe base settings, so its exact old traceback/root cause is not established. | Reset configuration before collection and per test; use Echo/local, temporary artifacts and in-memory DB. Default-isolation regression asserts these settings. |
| `test_loop_failed_runs_continue` | Same ambient settings dependency; if a different provider is selected, patching Echo does not affect it. Historical failure did not reproduce under safe base settings. | Same configuration fixture; external network guard ensures a leaked live client fails before connecting. The existing class patch is already restored in `finally`. |
| `test_live_mode_requires_key_before_constructing_client` | Removing the key alone is insufficient because the CLI calls dotenv again. | Disable dotenv for the entire pytest process and children; explicitly remove the key; inject a constructor that raises if created. |
| `test_nebius_smoke_test_fails_safely_when_credentials_missing` | Child script calls dotenv, which can reload a removed key; decoding previously depended on the terminal locale. Historical live credentials were not read or used to reproduce it. | Inherit dotenv-disable flag and cleared credentials; explicit UTF-8 and 30-second subprocess timeout. A fake dotenv-file child-process regression proves credentials cannot reload. |

Initial sandbox-only testing produced six temporary-directory permission errors (322 tests passed); running with normal temp-directory access resolved those infrastructure errors. An initial external-socket guard also rejected Windows asyncio's loopback socketpair; it now permits numeric loopback while rejecting external connections. Those diagnostic failures are resolved, not classified as pre-existing application failures.

No live provider request, GPU job or paid external-service test is required. Existing provider/cloud tests use injected clients; regression coverage rejects external sockets. The smoke test explicitly forces Echo/local and blocks external browser requests.

## Security and claim review

Tracked env files are templates only. No `.env` or `frontend/.env.local` history was found through the available refs. A targeted scan for common API-token, AWS-access-key and private-key patterns found the published AWS example key in a storage-client test fixture; no actual credential was identified by that scan. This is a limited pattern scan, not a complete historical secret-scanning certification. Personal env files were not opened. `.gitignore` now excludes env variants and keeps examples visible.

Pipeline and saved-provenance review is recorded in [pipeline-audit.md](pipeline-audit.md). Unknown interventions cannot silently receive affirmative support. Synthetic workload labels propagate through specs, execution results, saved history, API and dashboard. README setup, license, architecture, limitations, offline browser command and [2:40 demo/fallback](demo-walkthrough.md) are present.

## Remaining limitations and release decision

- Generated code is not a trusted measurement authority or securely sandboxed. The local API is intended for trusted local use.
- Nebius reasoning and GPU execution were not exercised live. No real-model speedup or GPU result is claimed.
- Generated analyst prose is interpretation; unknown interventions get a deterministic insufficient-evidence conclusion.
- A Starlette/AnyIO deprecation warning remains; it does not fail tests.

**Go for an offline synthetic-workflow demo once final-head CI is green. No-go for claims of verified model-inference optimization, GPU benchmarking or production containment.** Do not merge or submit automatically. Use the [ten-minute pre-demo checklist](demo-walkthrough.md#ten-minute-pre-demo-checklist).
