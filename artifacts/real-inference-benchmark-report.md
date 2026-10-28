# Real CPU Inference Benchmark — Run Report

**Benchmark ID:** `sklearn_digits_logistic_regression_cpu_inference`
**Run timestamp (UTC):** 2026-10-28T23:39:26.090688+00:00
**Machine-readable results:** [`artifacts/real-inference-benchmark.json`](real-inference-benchmark.json)
**Implementation:** [`experiments/real_inference_benchmark.py`](../experiments/real_inference_benchmark.py)
**Protocol documentation:** [`docs/real-inference-benchmark.md`](../docs/real-inference-benchmark.md)

## 1. Executive summary

A real scikit-learn classifier (`StandardScaler + LogisticRegression`) was fitted once on the bundled handwritten-digits dataset and then used to score the same 540 test samples in two ways: **row-wise** (one `predict_proba` call per sample) and **batched** (one `predict_proba` call for the full test set). Over 10 timed repetitions per method, the batched path was **263.27× faster** in median wall-clock latency (64.57925 ms vs 0.2453 ms for the complete test set). Both paths produced **identical predicted labels** (100% label parity) and probabilities differing by at most **1.11e-15** (floating-point noise). Model accuracy on the test set was **98.15%** for both paths.

This is a **local CPU measurement** on one specific machine, model, dataset, and software stack. It demonstrates an inference batching effect for this workload only — it is not a GPU, LLM-serving, TensorRT, or production benchmark, and the speedup is not guaranteed to transfer to other models, datasets, or hosts.

## 2. Purpose and research question

**Research question:** What changes in inference latency when the same fitted classifier processes test examples one at a time versus in a single batch?

The benchmark isolates the *inference* phase: dataset loading and model training are excluded from the timed region. The only difference between the two measured paths is the call pattern (540 individual calls vs 1 batched call) against the identical fitted model and identical test rows.

## 3. Hardware and software environment

| Item | Value |
| --- | --- |
| Python | 3.14.0 |
| Platform | Windows-11-10.0.26200-SP0 |
| Processor | AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD |
| scikit-learn | 1.9.1 |
| NumPy | 2.5.4 |
| Clock source | `time.perf_counter_ns` (wall-clock, nanosecond resolution) |

## 4. Dataset and model

| Item | Value |
| --- | --- |
| Dataset | scikit-learn bundled handwritten digits (`load_digits`) |
| Total samples | 1797 |
| Features | 64 (8×8 pixel images) |
| Classes | 10 |
| Train / test split | 1257 / 540 (30% test, stratified by label) |
| Split seed | 42 |
| Model | `StandardScaler` + `LogisticRegression(max_iter=2000, random_state=42)` |
| Training included in timing | No |

## 5. Experimental methodology

1. Load the digits dataset and create a stratified 70/30 train/test split with `random_state=42`.
2. Fit the pipeline once on the training split.
3. **Warm up** both paths (16 samples each) before any timed measurement.
4. **Parity check before timing:** run both paths once and verify (a) predicted labels are exactly equal and (b) record the maximum absolute probability difference. If labels differ, the run aborts as invalid.
5. **Timed measurement:** 10 repetitions per method. The measurement order **alternates** each repetition (even repeats: row-wise then batched; odd repeats: batched then row-wise) to reduce systematic order bias.
6. Each timed sample is the elapsed wall-clock time for processing the **entire 540-sample test set** with that method.
7. Report median, mean, standard deviation, min, and max per method, plus throughput at the median.

## 6. Baseline and batched inference procedures

- **Baseline (row-wise):** `model.predict_proba(row.reshape(1, -1))` called once per test row — 540 separate calls per repetition.
- **Candidate (batched):** `model.predict_proba(X_test)` called once for the full test matrix — 1 call per repetition.
- Both use the same fitted pipeline object and the same test rows in the same order.

## 7. Exact command used

```sh
python -m pip install -e ".[ml-benchmark]"
python -m experiments.real_inference_benchmark --repeats 10 --seed 42 --output artifacts/real-inference-benchmark.json
```

Run from the repository root on the machine described in §3.

## 8. Actual measured results

All values below are **observed measurements** from the run recorded in the JSON artifact. The latency metric is **total wall-clock milliseconds to process all 540 test samples** in one repetition (not per-sample).

| Statistic (ms, full test set) | Row-wise (baseline) | Batched (candidate) |
| --- | ---: | ---: |
| Median | 64.57925 | 0.2453 |
| Mean | 64.62765 | 0.24919 |
| Std dev | 0.7101097665541265 | 0.023434658568501104 |
| Min | 63.597 | 0.2241 |
| Max | 65.5928 | 0.2782 |
| Throughput at median (samples/s) | 8,361.82 | 2,201,386.06 |
| Test-set accuracy | 0.9814814814814815 (98.15%) | 0.9814814814814815 (98.15%) |

Per-sample medians (derived): row-wise ≈ 0.1196 ms/sample; batched ≈ 0.000454 ms/sample.

## 9. Label and probability parity

| Check | Result |
| --- | --- |
| Predicted labels match (row-wise vs batched) | **true** (exact equality, all 540 samples) |
| Max absolute probability difference | 1.1102230246251565e-15 |

The probability difference is at the level of floating-point rounding noise (≈1e-15), consistent with the two paths performing the same linear algebra in different call shapes.

## 10. Derived speedup

**Speedup = row-wise median latency ÷ batched median latency = 64.57925 ms ÷ 0.2453 ms = 263.266408479413 ≈ 263.27×**

This is a **derived metric** computed from the observed medians. It is a ratio of total-test-set latencies, so it is unit-independent (ms/ms).

## 11. Limitations, threats to validity, and reproducibility

**Limitations and threats to validity:**

- **Single host, single run.** Timings depend on CPU, OS scheduler, background load, and Python/NumPy/scikit-learn versions. No other machine or software configuration was tested.
- **Small, low-dimensional model.** Logistic regression on 64 features is a cheap model; the per-call overhead dominates the row-wise path. The 263.27× ratio reflects call-overhead amortization for *this* model shape and does not bound the effect for heavier models (e.g., deep networks), where per-sample compute may dominate and the ratio would be much smaller.
- **Wall-clock timing.** `time.perf_counter_ns` measures wall time; OS preemption or background activity can inflate individual samples (the row-wise max of 65.5928 ms vs median 64.57925 ms shows mild variance).
- **No independent attestation.** The numbers are self-reported by the benchmark script; no external instrumentation verified them.
- **Batched path is a single call.** This measures one batch of 540, not streaming/production serving with variable batch sizes, queuing, or concurrency.
- **Not a GPU/LLM benchmark.** Nothing here involves GPU execution, TensorRT, or LLM serving.

**Reproducibility:**

```sh
# From the repository root, in a Python >= 3.11 environment:
python -m pip install -e ".[ml-benchmark]"
python -m experiments.real_inference_benchmark --repeats 10 --seed 42 --output artifacts/real-inference-benchmark.json
python -m pytest tests/test_real_inference_benchmark.py -q
```

The split, model seed, and measurement protocol are fixed by the seed and the script, so label/accuracy results are deterministic; latency values will differ across hosts and runs.

## 12. Conclusion: evidence vs interpretation

**Evidence (what this run measured):**

- On this Windows 11 / Python 3.14.0 / scikit-learn 1.9.1 / NumPy 2.5.4 host, one batched `predict_proba` call over 540 digits samples took a median of 0.2453 ms, while 540 individual calls took a median of 64.57925 ms — a 263.27× median-latency ratio.
- Both paths produced identical labels and probabilities within 1.11e-15, and identical 98.15% test accuracy.

**Interpretation (what it suggests, and what it does not prove):**

- It suggests that **batching inference calls reduces per-call overhead** for this scikit-learn classifier on this hardware — the same computation is far cheaper when issued as one matrix operation than as 540 separate Python-level calls.
- It does **not** prove a universal batching speedup, a GPU speedup, an LLM-serving improvement, or a production deployment benefit. The magnitude (263.27×) is specific to this model, dataset size, and host, and should not be quoted without this context.
- It does **not** indicate that Nemotron or the hosted AXIOM orchestrator executed this experiment; it is a standalone local script.

## 13. Artifact references

- Machine-readable results: `artifacts/real-inference-benchmark.json`
- This report: `artifacts/real-inference-benchmark-report.md`
- Benchmark implementation: `experiments/real_inference_benchmark.py`
- Protocol documentation: `docs/real-inference-benchmark.md`
- Tests: `tests/test_real_inference_benchmark.py`