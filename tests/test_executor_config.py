"""Tests for executor backend configuration and artifact store abstraction."""

import os
import tempfile
from pathlib import Path

import pytest

from axiom.config import Settings
from axiom.domain.interfaces import ExperimentExecutor
from axiom.domain.models import ExperimentSpec, ExperimentRun, RunStatus
from axiom.execution.artifacts import ArtifactStore, LocalArtifactStore
from axiom.execution.local_executor import LocalExecutor
from axiom.services.research_loop import LoopServices


def test_default_executor_backend_is_local():
    """Default Settings should have executor_backend='local'."""
    settings = Settings()
    assert settings.executor_backend == "local"


def test_local_backend_selects_local_executor():
    """AXIOM_EXECUTOR_BACKEND=local should select LocalExecutor."""
    settings = Settings(executor_backend="local")
    services = LoopServices.from_settings(settings)
    assert isinstance(services.executor, LocalExecutor)
    assert isinstance(services.artifact_store, LocalArtifactStore)
    assert isinstance(services.artifact_store, ArtifactStore)


def test_unsupported_executor_backend_raises():
    """Unsupported executor backend should raise a clear RuntimeError."""
    settings = Settings(executor_backend="unsupported_backend")
    with pytest.raises(RuntimeError, match="Unsupported executor backend"):
        LoopServices.from_settings(settings)


def test_nebius_gpu_backend_creates_executor():
    """Selecting nebius_gpu should create a NebiusGPUExecutor with RealNebiusJobClient."""
    from axiom.execution.nebius_gpu_executor import NebiusGPUExecutor
    from axiom.execution.nebius_cloud_job_client import RealNebiusJobClient

    settings = Settings(executor_backend="nebius_gpu")
    services = LoopServices.from_settings(settings)
    assert isinstance(services.executor, NebiusGPUExecutor)
    assert isinstance(services.executor.job_client, RealNebiusJobClient)


def test_loop_services_dependency_injection_still_works():
    """LoopServices should allow direct dependency injection of executors and artifact stores."""
    class DummyExecutor(ExperimentExecutor):
        def execute(self, spec, timeout_seconds):
            return ExperimentRun(experiment_id=spec.id, status=RunStatus.COMPLETED)

    with tempfile.TemporaryDirectory() as tmp:
        store = LocalArtifactStore(root=tmp)
        from axiom.agents.analyst import AnalystAgent
        from axiom.agents.planner import PlannerAgent
        from axiom.agents.researcher import ResearcherAgent
        from axiom.providers.echo_provider import EchoReasoningProvider
        from axiom.execution.evaluator import DeterministicEvaluator
        from axiom.memory.sqlite_repo import SqliteRepository

        provider = EchoReasoningProvider()
        services = LoopServices(
            provider=provider,
            researcher=ResearcherAgent(provider),
            planner=PlannerAgent(provider),
            analyst=AnalystAgent(provider),
            executor=DummyExecutor(),
            evaluator=DeterministicEvaluator(),
            repository=SqliteRepository(db_path=":memory:"),
            artifact_store=store,
        )
        assert services.executor is not None
        assert services.artifact_store is store


def test_local_executor_behavior_unchanged():
    """LocalExecutor should still write code, run it, parse metrics, and save manifest."""
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalArtifactStore(root=tmp)
        executor = LocalExecutor(artifact_store=store)
        # Simple script that prints a metrics line
        code = (
            "import sys\n"
            "import json\n"
            "print('hello world')\n"
            "print(json.dumps({'metrics': [{'name': 'test_metric', 'value': 42.0}]}))\n"
        )
        spec = ExperimentSpec(
            plan_id="plan_123",
            name="test_spec",
            description="test",
            code=code,
        )
        run = executor.execute(spec, timeout_seconds=10.0)
        assert run.status == RunStatus.COMPLETED
        assert run.exit_code == 0
        assert "hello world" in run.stdout
        assert len(run.metrics) == 1
        assert run.metrics[0].name == "test_metric"
        assert run.metrics[0].value == 42.0
        # Check that run manifest was saved as an artifact
        assert len(run.artifacts) == 1
        assert run.artifacts[0].name == "run_manifest.json"
        # Verify we can read it back
        manifest_data = store.read(run.artifacts[0])
        assert b"run_id" in manifest_data


def test_artifact_store_abstraction_preserves_local_behavior():
    """ArtifactStore abstraction should preserve existing local filesystem behavior."""
    with tempfile.TemporaryDirectory() as tmp:
        # ArtifactStore() should instantiate LocalArtifactStore
        store = ArtifactStore(root=tmp)
        assert isinstance(store, LocalArtifactStore)
        # Save an artifact
        content = b"some test content"
        artifact = store.save_output("run_1", "output.txt", content)
        assert artifact.name == "output.txt"
        assert artifact.sha256 is not None
        assert artifact.size_bytes == len(content)
        # Verify path is under the run directory
        assert str(Path(artifact.path).parent) == str(Path(tmp) / "run_1")
        # Read it back
        read_content = store.read(artifact)
        assert read_content == content


def test_artifact_sha256_verification_still_works():
    """ArtifactStore should verify SHA-256 digest on read."""
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalArtifactStore(root=tmp)
        content = b"verify me"
        artifact = store.save_output("run_sha", "data.bin", content)
        # Normal read works
        assert store.read(artifact) == content
        # Corrupt the file on disk
        Path(artifact.path).write_bytes(b"corrupted")
        with pytest.raises(ValueError, match="integrity check failed"):
            store.read(artifact)


def test_immutable_artifact_behavior_still_works():
    """ArtifactStore should reject overwriting existing artifacts."""
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalArtifactStore(root=tmp)
        store.save_output("run_imm", "out.txt", b"first")
        # Attempting to save the same artifact again should raise FileExistsError
        with pytest.raises(FileExistsError, match="already exists; run outputs are immutable"):
            store.save_output("run_imm", "out.txt", b"second")


def test_executor_backend_env_var():
    """AXIOM_EXECUTOR_BACKEND environment variable should be read."""
    os.environ["AXIOM_EXECUTOR_BACKEND"] = "local"
    try:
        settings = Settings()
        assert settings.executor_backend == "local"
    finally:
        del os.environ["AXIOM_EXECUTOR_BACKEND"]


def test_nebius_gpu_config_fields_present():
    """Settings should have placeholder fields for future GPU executor."""
    settings = Settings()
    assert hasattr(settings, "nebius_gpu_instance_type")
    assert hasattr(settings, "nebius_gpu_count")
    assert hasattr(settings, "nebius_container_image")
    assert hasattr(settings, "nebius_artifact_store_uri")
    assert hasattr(settings, "nebius_max_wall_time_seconds")
    # Default values should be reasonable
    assert settings.nebius_gpu_count >= 1
    assert settings.nebius_max_wall_time_seconds > 0