# Experiment pipeline audit

## Canonical path

1. API routes parse a user objective and save it in SQLite.
2. Researcher asks the configured reasoning provider for a structured hypothesis.
3. Planner asks for `PlanOutput` and `CodeOutput`, enforces the objective metric, and normalizes escaped code. It keeps valid Python untouched; existing normalization regressions cover escapes, raw strings, regular expressions and backslashes.
4. The spec is synthetic by default. Generated code is preserved; a conflicting `LEVER` constant is not renamed to manufacture agreement.
5. Engine creates baseline/candidate specs from the same code and parameters, forcing both `EXPERIMENT_MODE` and `__AXIOM_LEVER_MODE__`. It validates both before any executor call.
6. Local executor writes UTF-8 Python in a temporary directory, executes it in a subprocess, captures UTF-8 output, parses metric JSON, and saves a run manifest. Runs and aggregate results retain the workload label.
7. Deterministic evaluator compares executor-produced samples. No reasoning provider supplies an `Evaluation` or authoritative numeric measurement directly to this evaluator.
8. Analyst receives the computed evaluation. The loop adds the intervention limitation; unverified or conflicting implementations cannot receive an affirmative hypothesis-support verdict. The numerical target flag remains a statement about the script's metrics, not proof of the proposed mechanism.
9. SQLite saves hypothesis, plan, both specs, individual and aggregate runs, evaluation and evidence. API history rehydrates this chain. Dashboard provenance supports fresh summaries and saved history.

## What is verified

The known Echo implementation times arithmetic with `time.perf_counter`. Candidate mode reduces loop counts: batch_size 8,000,000 -> 4,000,000; threads 8,000,000 -> 4,800,000; precision 16,000,000 -> 8,000,000. These names refer to synthetic variants. The threads function is not multithreaded and the precision function does not quantize a model. Planned settings now record the arithmetic iteration counts.

The planner marks an intervention `verified_synthetic` only when the generated code exactly matches the known Echo implementation and its planned variable values agree. Other generated implementations remain `insufficient`, or `mismatch` when declarations conflict. This is a conservative implementation identity check, not an attestation system. A stored label is not a trusted security assertion against database tampering.

Matching frontend declarations are labelled as consistency only. Planned values are distinguished from spec parameters/environment; an explicit intervention explanation identifies what is verified. Real-inference workload labels are declarations, not independently verified proof.

## Limitations

- An LLM can generate a script that prints fabricated metrics. Parsing stdout does not prove physical measurements. Unknown scripts therefore cannot establish hypothesis support merely by printing an apparent speedup.
- AST validation rejects obvious hazards but is bypassable; local subprocesses retain host filesystem/network capabilities. Temporary cwd and reduced environment do not constitute containment. POSIX resource limits are best effort and unavailable on Windows; child process trees are not a hardened sandbox.
- No live Nebius reasoning request, GPU job, object-storage request, quantization benchmark or model-inference speedup was executed in this audit.
- Generated analyst prose is interpretation. The conservative conclusion guard prevents affirmative support for unverified interventions but does not independently fact-check every generated sentence.
- Timing varies with host load. Synthetic speedup thresholds are integration checks, not statistically rigorous performance claims.
- The legacy modules under `backend/` and the canonical `backend/axiom/` stack coexist. The documented app is `backend.main:app`; canonical settings govern the dashboard.

## Smallest real-inference follow-up (separate scope)

Introduce a reviewed fixed benchmark adapter, rather than arbitrary generated measurement code. Pin model/revision, tokenizer, dataset, sample order, warmup, repetition count and hardware/software versions. Validate one treatment (for example a batch-size change) against a fixed configuration schema. An external harness must time both conditions using a monotonic clock, synchronize GPU work if applicable, capture raw samples, check output-quality parity, and save an immutable manifest and implementation hash. Only this adapter should be allowed to emit verified real-inference provenance. Run it in a disposable container/VM with explicit resource and network policies, then perform a separately authorized paid smoke test. Keep reasoning-provider requests distinct from benchmark-inference requests and costs.
