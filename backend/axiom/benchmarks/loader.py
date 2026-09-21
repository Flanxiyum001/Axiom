"""Dataset loading: files, dicts, and JSON text with graceful errors."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from axiom.benchmarks.models import BenchmarkDataset

_EXAMPLE_PATH = Path(__file__).parent / "datasets" / "example_benchmark.json"


class BenchmarkLoadError(ValueError):
    """Raised when benchmark data cannot be loaded or validated."""


def load_dict(data: dict) -> BenchmarkDataset:
    """Validate raw mapping data into a dataset, wrapping schema errors."""
    if not isinstance(data, dict):
        raise BenchmarkLoadError(f"Dataset must be a mapping, got {type(data).__name__}")
    try:
        return BenchmarkDataset.model_validate(data)
    except ValidationError as exc:
        raise BenchmarkLoadError(f"Invalid benchmark dataset: {exc}") from exc


def loads(text: str) -> BenchmarkDataset:
    """Parse JSON text into a validated dataset."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BenchmarkLoadError(f"Invalid benchmark JSON: {exc}") from exc
    return load_dict(data)


def load_file(path: str | Path) -> BenchmarkDataset:
    """Read and validate a dataset file without leaking OS errors."""
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise BenchmarkLoadError(f"Cannot read benchmark file {source}: {exc}") from exc
    try:
        return loads(text)
    except BenchmarkLoadError as exc:
        raise BenchmarkLoadError(f"{source}: {exc}") from exc


def load_example() -> BenchmarkDataset:
    """Load the bundled example dataset shipped with the package."""
    return load_file(_EXAMPLE_PATH)
