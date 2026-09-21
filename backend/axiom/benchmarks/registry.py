"""Named dataset registry: share datasets without touching core code."""

from __future__ import annotations

import copy

from axiom.benchmarks.models import BenchmarkDataset

_DATASETS: dict[str, BenchmarkDataset] = {}


def register(dataset: BenchmarkDataset) -> None:
    """Add or replace the dataset stored under its name."""
    _DATASETS[dataset.name] = dataset


def get_dataset(name: str) -> BenchmarkDataset:
    """Return an isolated copy of the named dataset."""
    if name not in _DATASETS:
        raise KeyError(f"Unknown benchmark dataset {name!r}; known: {sorted(_DATASETS)}")
    return copy.deepcopy(_DATASETS[name])


def list_datasets() -> list[str]:
    """Names of all registered datasets in registration order."""
    return list(_DATASETS)


def clear() -> None:
    """Remove all registrations; primarily useful for isolated tests."""
    _DATASETS.clear()
