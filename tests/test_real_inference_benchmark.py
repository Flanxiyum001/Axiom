from __future__ import annotations

import pytest

from experiments.real_inference_benchmark import run_benchmark, summarize


def test_summarize_returns_descriptive_statistics() -> None:
    result = summarize([1.0, 2.0, 3.0])

    assert result["median_ms"] == 2.0
    assert result["mean_ms"] == 2.0
    assert result["stdev_ms"] == 1.0
    assert result["min_ms"] == 1.0
    assert result["max_ms"] == 3.0


def test_summarize_rejects_empty_samples() -> None:
    with pytest.raises(ValueError, match="At least one"):
        summarize([])


def test_benchmark_requires_multiple_repetitions() -> None:
    with pytest.raises(ValueError, match="at least 3 repeats"):
        run_benchmark(repeats=2)
