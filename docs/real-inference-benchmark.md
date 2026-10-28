# Reproducible real-ML inference benchmark

This benchmark addresses one narrow question: **what changes when the same fitted classifier processes test examples one at a time versus in a single batch?**

It is a real CPU ML inference experiment using scikit-learn's bundled handwritten-digits dataset and a \`StandardScaler\` + \`LogisticRegression\` classifier. It is deliberately separate from the hosted synthetic CPU demonstration.

## Run it

\`\`\`sh
python -m pip install -e '.[ml-benchmark]'
python -m experiments.real_inference_benchmark --repeats 10 --seed 42 --output artifacts/real-inference-benchmark.json
\`\`\`

The command trains a fixed model and uses a fixed stratified train/test split. Training and dataset loading are excluded from the timed inference region. The report is printed to stdout and optionally written to the specified JSON path.

## What is compared

- **Baseline:** call \`predict_proba\` separately for every test row.
- **Candidate:** call \`predict_proba\` once for the full test batch.
- Both methods use the **same fitted model and identical test examples**.
- Each method is warmed up before timing. Timed order alternates between repetitions.
- The report records timing summary statistics, median latency, throughput, accuracy, environment, dataset dimensions, and configuration.
- The benchmark checks that both paths return the same predicted labels before accepting the timing comparison. It also reports the maximum absolute probability difference.

The primary comparison is median wall-clock latency for processing the complete test set. Speedup is computed as baseline median latency divided by candidate median latency. The script requires at least three timed repetitions; ten or more is recommended for a demo run.

## Interpreting the report

A result is meaningful only with its context. A batched call can reduce per-call overhead, but the size of the effect depends on CPU, Python, NumPy/scikit-learn versions, process load, and test-set size. Run it on the same machine and environment for a baseline/candidate comparison.

- A speedup is **not guaranteed**. Report what the run measures; do not hard-code a result into the UI or README.
- Matching predictions is a functional-equivalence check for this workload, not proof of correctness for every model or dataset.
- Timings are local CPU measurements, not GPU, LLM-serving, TensorRT, or production-service measurements.
- This script is a standalone reproducible experiment; it is not yet wired into the hosted research workspace or automatically selected by Nemotron.

## Evidence and reproducibility

The JSON report includes the Python/platform information, scikit-learn and NumPy versions, split seed, train/test counts, model settings, repeated timing summaries, throughput, accuracy, and equivalence checks. Preserve the report alongside any presentation of the result. Do not present a result without the host/configuration and the exact report.

This is the first concrete real-ML measurement path; it does not replace AXIOM's existing synthetic hosted demo. The demo's synthetic timings and this local classifier benchmark must remain separately labelled.
