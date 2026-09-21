"""Dataset handling: schemas, loading, registry, and runner consumption."""

import json
import tempfile
from pathlib import Path

from axiom.benchmarks import registry
from axiom.benchmarks.loader import (
    BenchmarkLoadError,
    load_dict,
    load_example,
    load_file,
    loads,
)
from axiom.experiments.runner import ExperimentRequest


def _valid_payload():
    """Minimal valid dataset payload used across loading tests."""
    return {
        "name": "test_benchmark",
        "description": "test",
        "cases": [
            {
                "id": "case-001",
                "input": "What is 2+2?",
                "expected_output": "4",
                "metadata": {"topic": "math"},
                "evaluation": {"latency_budget_ms": 1000.0},
            }
        ],
    }


def test_load_dict_accepts_valid_dataset():
    """Well-formed mappings validate into datasets with intact cases."""
    dataset = load_dict(_valid_payload())
    assert dataset.name == "test_benchmark"
    assert dataset.case_ids() == ["case-001"]
    case = dataset.get_case("case-001")
    assert case is not None
    assert case.expected_output == "4"
    assert case.metadata == {"topic": "math"}
    assert case.evaluation.latency_budget_ms == 1000.0


def test_load_dict_rejects_non_mapping():
    """Non-mapping input fails with a load error, not a crash."""
    for bad in (None, [], "text", 42):
        try:
            load_dict(bad)
        except BenchmarkLoadError:
            continue
        raise AssertionError(f"expected BenchmarkLoadError for {bad!r}")


def test_loads_parses_json_text():
    """JSON text parses and validates like an equivalent mapping."""
    assert loads(json.dumps(_valid_payload())).name == "test_benchmark"


def test_loads_rejects_malformed_json():
    """Broken JSON fails with a load error naming the syntax problem."""
    try:
        loads("{not json")
    except BenchmarkLoadError as exc:
        assert "JSON" in str(exc)
        return
    raise AssertionError("expected BenchmarkLoadError")


def test_loads_rejects_schema_violations():
    """Missing names, blank ids, and empty case lists all fail validation."""
    cases = [
        {"cases": [{"id": "a", "input": "q"}]},
        {"name": "", "cases": [{"id": "a", "input": "q"}]},
        {"name": "x", "cases": []},
        {"name": "x", "cases": [{"id": "", "input": "q"}]},
        {"name": "x", "cases": [{"id": "a", "input": ""}]},
    ]
    for payload in cases:
        try:
            load_dict(payload)
        except BenchmarkLoadError:
            continue
        raise AssertionError(f"expected BenchmarkLoadError for {payload!r}")


def test_load_rejects_duplicate_case_ids():
    """Two cases sharing an id fail with the offending id named."""
    payload = _valid_payload()
    payload["cases"].append({"id": "case-001", "input": "Other question"})
    try:
        load_dict(payload)
    except BenchmarkLoadError as exc:
        assert "case-001" in str(exc)
        return
    raise AssertionError("expected BenchmarkLoadError")


def test_load_rejects_bad_evaluation_config():
    """Non-positive evaluator tuning fails instead of misbehaving later."""
    payload = _valid_payload()
    payload["cases"][0]["evaluation"] = {"latency_budget_ms": -5}
    try:
        load_dict(payload)
    except BenchmarkLoadError:
        return
    raise AssertionError("expected BenchmarkLoadError")


def test_load_file_roundtrip():
    """Datasets survive a write/read cycle through real files."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bench.json"
        path.write_text(json.dumps(_valid_payload()), encoding="utf-8")
        assert load_file(path).name == "test_benchmark"


def test_load_file_missing_path():
    """Unreadable paths fail with a load error, not an OS exception."""
    try:
        load_file("/nonexistent/bench.json")
    except BenchmarkLoadError:
        return
    raise AssertionError("expected BenchmarkLoadError")


def test_bundled_example_loads():
    """The shipped example dataset matches the documented format."""
    dataset = load_example()
    assert dataset.name == "example_benchmark"
    assert len(dataset.cases) >= 2
    assert dataset.get_case("missing") is None


def test_case_converts_to_runner_request():
    """Cases expose runner input with metadata as context, no provider tie-in."""
    dataset = load_example()
    request = dataset.cases[0].to_request(system="Be concise.")
    assert isinstance(request, ExperimentRequest)
    assert request.prompt == dataset.cases[0].input
    assert request.system == "Be concise."
    assert request.context == dataset.cases[0].metadata


def test_registry_stores_and_isolates():
    """Registered datasets are retrievable; callers get copies, not handles."""
    registry.clear()
    try:
        dataset = load_dict(_valid_payload())
        registry.register(dataset)
        assert registry.list_datasets() == ["test_benchmark"]
        fetched = registry.get_dataset("test_benchmark")
        assert fetched == dataset
        fetched.cases[0].input = "MUTATED"
        assert registry.get_dataset("test_benchmark").cases[0].input == "What is 2+2?"
    finally:
        registry.clear()


def test_registry_unknown_name():
    """Unknown names fail naming the lookup and the known datasets."""
    registry.clear()
    try:
        registry.get_dataset("nope")
    except KeyError as exc:
        assert "nope" in str(exc)
        return
    raise AssertionError("expected KeyError")
