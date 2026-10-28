"""Reproducible CPU ML inference benchmark: row-wise vs batched prediction.

This benchmark uses scikit-learn's bundled handwritten-digits dataset and a
real LogisticRegression classifier. It measures inference only; model training
and dataset loading are excluded. The baseline invokes the model once per row,
while the candidate invokes the same model once for the complete batch.

Run:
    python -m pip install -e '.[ml-benchmark]'
    python -m experiments.real_inference_benchmark --repeats 10

This is a local CPU experiment, not a GPU benchmark. Timings depend on the host.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


def summarize(samples_ms: Sequence[float]) -> dict[str, float]:
    """Return transparent descriptive statistics for a non-empty sample list."""
    if not samples_ms:
        raise ValueError("At least one timing sample is required")
    return {
        "median_ms": statistics.median(samples_ms),
        "mean_ms": statistics.mean(samples_ms),
        "stdev_ms": statistics.stdev(samples_ms) if len(samples_ms) > 1 else 0.0,
        "min_ms": min(samples_ms),
        "max_ms": max(samples_ms),
    }


def time_call(fn: Callable[[], object]) -> float:
    """Return elapsed wall-clock time in milliseconds."""
    start = time.perf_counter_ns()
    fn()
    return (time.perf_counter_ns() - start) / 1_000_000


def run_benchmark(*, repeats: int = 10, seed: int = 42) -> dict:
    """Train a fixed classifier and compare row-wise with batched CPU inference."""
    if repeats < 3:
        raise ValueError("Use at least 3 repeats to make timing variation visible")

    try:
        import numpy as np
        import sklearn
        from sklearn.datasets import load_digits
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise RuntimeError(
            "Benchmark dependencies are missing. Install with: "
            "python -m pip install -e '.[ml-benchmark]'"
        ) from exc

    dataset = load_digits()
    X_train, X_test, y_train, y_test = train_test_split(
        dataset.data,
        dataset.target,
        test_size=0.30,
        random_state=seed,
        stratify=dataset.target,
    )

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=2000, random_state=seed),
    )
    model.fit(X_train, y_train)

    # Warm both paths before timing. Training and data loading are not measured.
    _ = model.predict_proba(X_test[: min(16, len(X_test))])
    _ = [model.predict_proba(row.reshape(1, -1)) for row in X_test[: min(16, len(X_test))]]

    def rowwise_predict() -> list:
        return [model.predict_proba(row.reshape(1, -1))[0] for row in X_test]

    def batched_predict():
        return model.predict_proba(X_test)

    # Verify functional equivalence before collecting performance numbers.
    rowwise_probabilities = np.asarray(rowwise_predict())
    batched_probabilities = batched_predict()
    rowwise_labels = np.argmax(rowwise_probabilities, axis=1)
    batched_labels = np.argmax(batched_probabilities, axis=1)
    predictions_match = bool(np.array_equal(rowwise_labels, batched_labels))
    max_probability_abs_difference = float(
        np.max(np.abs(rowwise_probabilities - batched_probabilities))
    )
    if not predictions_match:
        raise RuntimeError("Benchmark invalid: row-wise and batched predictions differ")

    # Alternate order to reduce systematic bias from always running one path first.
    rowwise_samples: list[float] = []
    batched_samples: list[float] = []
    for index in range(repeats):
        if index % 2 == 0:
            rowwise_samples.append(time_call(rowwise_predict))
            batched_samples.append(time_call(batched_predict))
        else:
            batched_samples.append(time_call(batched_predict))
            rowwise_samples.append(time_call(rowwise_predict))

    rowwise_summary = summarize(rowwise_samples)
    batched_summary = summarize(batched_samples)
    baseline_median = rowwise_summary["median_ms"]
    candidate_median = batched_summary["median_ms"]
    speedup = baseline_median / candidate_median if candidate_median > 0 else None
    rowwise_accuracy = float(np.mean(rowwise_labels == y_test))
    batched_accuracy = float(np.mean(batched_labels == y_test))

    return {
        "schema_version": 1,
        "benchmark": "sklearn_digits_logistic_regression_cpu_inference",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": (
            "Real scikit-learn CPU inference on the bundled digits dataset. "
            "Not a GPU, LLM, or production-serving benchmark. Results are host-dependent."
        ),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "processor": platform.processor() or "not reported by operating system",
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
        },
        "dataset": {
            "name": "scikit-learn bundled handwritten digits",
            "samples_total": int(len(dataset.data)),
            "training_samples": int(len(X_train)),
            "test_samples": int(len(X_test)),
            "features": int(X_train.shape[1]),
            "classes": int(len(np.unique(dataset.target))),
            "split_seed": seed,
        },
        "model": {
            "type": "StandardScaler + LogisticRegression",
            "max_iter": 2000,
            "random_state": seed,
            "training_time_included_in_inference_measurement": False,
        },
        "measurement": {
            "repeats_per_method": repeats,
            "warmup_per_method": True,
            "clock": "time.perf_counter_ns",
            "metric": "elapsed wall-clock milliseconds for all test samples",
            "comparison": "same fitted model and same test set; row-wise vs one batched call",
            "rowwise": {
                **rowwise_summary,
                "samples_per_second_at_median": len(X_test) / (baseline_median / 1000),
                "accuracy": rowwise_accuracy,
            },
            "batched": {
                **batched_summary,
                "samples_per_second_at_median": len(X_test) / (candidate_median / 1000),
                "accuracy": batched_accuracy,
            },
            "median_latency_speedup": speedup,
            "prediction_labels_match": predictions_match,
            "max_probability_absolute_difference": max_probability_abs_difference,
        },
        "interpretation": (
            "A measured speedup applies only to this CPU workload, model, data, "
            "and execution setup. It does not imply a GPU or LLM speedup."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=10, help="timed repetitions per method (minimum 3)")
    parser.add_argument("--seed", type=int, default=42, help="fixed train/test split and model seed")
    parser.add_argument("--output", type=Path, help="optional path to write the JSON report")
    args = parser.parse_args()

    try:
        report = run_benchmark(repeats=args.repeats, seed=args.seed)
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
