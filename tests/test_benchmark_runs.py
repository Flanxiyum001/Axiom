"""Run persistence: save/load roundtrips, failures, listing, serialization."""

import json
import tempfile
from pathlib import Path

import pytest
from pydantic import BaseModel

from axiom.benchmarks.loader import load_dict
from axiom.domain.interfaces import ProviderError, ReasoningProvider
from axiom.evaluation.evaluators import LatencyEvaluator, ResponseEvaluator
from axiom.evaluation.framework import EvaluationFramework
from axiom.experiments.runner import ExperimentRunner
from axiom.pipeline.pipeline import ExperimentPipeline
from axiom.runs.models import BenchmarkRunStatus
from axiom.runs.recording import record_run
from axiom.runs.store import FileRunStore, RunNotFoundError, RunStoreError


class TextOutput(BaseModel):
    """Deterministic stub output for persistence tests."""

    answer: str


class StubProvider(ReasoningProvider):
    """Test double answering from the prompt or failing on demand."""

    name = "stub"

    def __init__(self, error=None):
        """Optionally fail every provider call with the given error."""
        self.error = error

    def generate(self, *, system, prompt, context, output_type):
        """Return canned text or raise the configured error."""
        if self.error is not None:
            raise self.error
        return TextOutput(answer=f"Answer to {prompt}")


def _dataset():
    """Small two-case dataset for persistence tests."""
    return load_dict(
        {
            "name": "persist_benchmark",
            "description": "persistence test",
            "cases": [
                {"id": "case-001", "input": "First question?"},
                {"id": "case-002", "input": "Second question?"},
            ],
        }
    )


def _pipeline(provider=None):
    """Pipeline with fast budgets for persistence tests."""
    return ExperimentPipeline(
        ExperimentRunner(provider or StubProvider()),
        EvaluationFramework([LatencyEvaluator(60000.0), ResponseEvaluator()]),
    )


def _run(**overrides):
    """Record a two-case pipeline run with overridable recorder options."""
    result = _pipeline().run(_dataset(), output_type=TextOutput, label="persist")
    options = {
        "system": "Be concise.",
        "output_schema": "TextOutput",
        "dataset_description": "persistence test",
        "max_concurrency": 2,
    }
    options.update(overrides)
    return record_run(result, **options)


def test_save_load_roundtrip():
    """Saved runs load back with identical content."""
    with tempfile.TemporaryDirectory() as tmp:
        store = FileRunStore(tmp)
        run = _run()
        store.save(run)
        assert store.exists(run.id)
        assert store.list_runs() == [run.id]
        assert store.load(run.id).model_dump() == run.model_dump()


def test_serialization_deterministic():
    """Equivalent runs serialize to equivalent bytes."""
    run = _run()
    assert run.model_dump_json(indent=2) == run.model_dump_json(indent=2)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp, f"{run.id}.json")
        assert not raw.exists()
        FileRunStore(tmp).save(run)
        assert json.loads(raw.read_text(encoding="utf-8"))["id"] == run.id


def test_ids_unique_and_prefixed():
    """Separate runs receive distinct stable brun_ identifiers."""
    first, second = _run(), _run()
    assert first.id != second.id
    assert first.id.startswith("brun_")
    assert second.id.startswith("brun_")


def test_missing_run_raises_not_found():
    """Unknown IDs raise a keyed error instead of returning None."""
    with tempfile.TemporaryDirectory() as tmp:
        store = FileRunStore(tmp)
        assert not store.exists("brun_missing")
        try:
            store.load("brun_missing")
        except RunNotFoundError as exc:
            assert "brun_missing" in str(exc)
            return
        raise AssertionError("expected RunNotFoundError")


def test_corrupt_file_surfaces_store_error():
    """Unparseable stored data raises a storage error, not raw exceptions."""
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "brun_bad.json").write_text("{not json", encoding="utf-8")
        try:
            FileRunStore(tmp).load("brun_bad")
        except RunStoreError:
            return
        raise AssertionError("expected RunStoreError")


def test_failed_cases_survive_roundtrip():
    """Mixed success and failure records persist with their errors."""
    result = _pipeline(provider=StubProvider(error=ProviderError("down"))).run(
        _dataset(), output_type=TextOutput
    )
    run = record_run(result)
    assert run.status == BenchmarkRunStatus.COMPLETED
    assert len(run.records) == 2
    with tempfile.TemporaryDirectory() as tmp:
        store = FileRunStore(tmp)
        store.save(run)
        back = store.load(run.id)
        assert back.model_dump() == run.model_dump()
        assert back.report.summary_for("response").failed == 2


def test_partial_run_status_and_config():
    """Unexpected case errors yield partial status with recorded failures."""
    runner = ExperimentRunner(StubProvider())
    original = runner.run

    def broken(request, *, output_type):
        if "Second" in request.prompt:
            raise RuntimeError("kaput")
        return original(request, output_type=output_type)

    runner.run = broken
    pipeline = ExperimentPipeline(runner, EvaluationFramework([ResponseEvaluator()]))
    result = pipeline.run(_dataset(), output_type=TextOutput)
    run = record_run(result)
    assert run.status == BenchmarkRunStatus.PARTIAL
    assert len(run.failures) == 1
    assert run.failures[0].stage == "run"
    assert run.config.case_ids == ["case-001", "case-002"]
    with tempfile.TemporaryDirectory() as tmp:
        store = FileRunStore(tmp)
        store.save(run)
        assert store.load(run.id).status == BenchmarkRunStatus.PARTIAL


def test_config_preservation():
    """Execution configuration survives the roundtrip intact."""
    run = _run(seed=7, temperature=0.5, extra={"note": "persist"})
    assert run.config.dataset == "persist_benchmark"
    assert run.config.dataset_description == "persistence test"
    assert run.config.label == "persist"
    assert run.config.system == "Be concise."
    assert run.config.output_schema == "TextOutput"
    assert run.config.providers == ["stub"]
    assert run.config.evaluator_names == ["latency", "response"]
    assert run.config.max_concurrency == 2
    assert run.config.seed == 7
    assert run.config.temperature == 0.5
    with tempfile.TemporaryDirectory() as tmp:
        store = FileRunStore(tmp)
        store.save(run)
        assert store.load(run.id).config == run.config


def test_list_runs_sorted():
    """Stored runs list in sorted ID order regardless of save order."""
    with tempfile.TemporaryDirectory() as tmp:
        store = FileRunStore(tmp)
        runs = [_run() for _ in range(3)]
        for run in reversed(runs):
            store.save(run)
        assert store.list_runs() == sorted(run.id for run in runs)


def test_record_rejects_non_pipeline_input():
    """Recording non-pipeline input raises instead of fabricating a run."""
    try:
        record_run({"benchmark": "x"})
    except TypeError:
        return
    raise AssertionError("expected TypeError")


def test_store_rejects_escaping_ids():
    """Run IDs that escape the store directory are refused as invalid."""
    with tempfile.TemporaryDirectory() as tmp:
        store = FileRunStore(tmp)
        for bad in ("../evil", "a/b", ""):
            with pytest.raises(ValueError):
                store.load(bad)


def test_list_skips_unrelated_files():
    """Foreign JSON files never appear in listings yet stay load-strict."""
    with tempfile.TemporaryDirectory() as tmp:
        store = FileRunStore(tmp)
        run = _run()
        store.save(run)
        Path(tmp, "notes.json").write_text('{"note": "not a run"}', encoding="utf-8")
        Path(tmp, "corrupt.json").write_text("{broken", encoding="utf-8")
        assert store.list_runs() == [run.id]
        with pytest.raises(RunStoreError):
            store.load("notes")


def test_list_read_failure_raises_store_error():
    """Unreadable candidates fail listing loudly instead of vanishing silently."""
    with tempfile.TemporaryDirectory() as tmp:
        store = FileRunStore(tmp)
        run = _run()
        store.save(run)
        original = Path.read_bytes

        def failing_read(self):
            if self.name == f"{run.id}.json":
                raise OSError("disk gone")
            return original(self)

        Path.read_bytes = failing_read
        try:
            with pytest.raises(RunStoreError):
                store.list_runs()
        finally:
            Path.read_bytes = original


def test_list_skips_id_filename_mismatch():
    """Valid run JSON under the wrong filename never produces a misleading ID."""
    with tempfile.TemporaryDirectory() as tmp:
        store = FileRunStore(tmp)
        run = _run()
        store.save(run)
        payload = Path(tmp, f"{run.id}.json").read_bytes()
        Path(tmp, "brun_impostor.json").write_bytes(payload)
        assert store.list_runs() == [run.id]
