"""Tests for NebiusGPUExecutor and NebiusJobClient integration."""

from __future__ import annotations

import tempfile
import time
from unittest.mock import MagicMock, patch
from datetime import UTC, datetime
from pathlib import Path

import pytest

from axiom.config import Settings
from axiom.domain.models import Artifact, ExperimentRun, ExperimentSpec, MetricSample, RunStatus
from axiom.execution.artifacts import LocalArtifactStore
from axiom.execution.nebius_gpu_executor import (
    NebiusGPUExecutor,
    NebiusStorageArtifactClient,
    integrate_nebius_artifact_retrieval,
)
from axiom.execution.nebius_storage_client import (
    NebiusStorageError,
    NebiusStorageAuthError,
    NebiusStorageNotFoundError,
    NebiusStorageConfigError,
)

from axiom.execution.nebius_job_client import (
    JobArtifacts,
    JobHandle,
    JobState,
    JobStatus,
    NebiusJobClient,
)


class FakeNebiusJobClient(NebiusJobClient):
    """Deterministic fake job client for testing NebiusGPUExecutor."""

    def __init__(self, behavior: str = "success") -> None:
        self.behavior = behavior
        self.submitted_specs: list[ExperimentSpec] = []
        self.cancelled_job_ids: list[str] = []
        self._poll_count = 0

    def submit(self, spec: ExperimentSpec) -> JobHandle:
        self.submitted_specs.append(spec)
        if self.behavior == "submit_error":
            raise RuntimeError("API rate limit exceeded")
        return JobHandle(job_id="job_nebius_12345")

    def get_status(self, job_id: str) -> JobState:
        self._poll_count += 1
        if self.behavior == "poll_error":
            if self._poll_count > 1:
                raise ConnectionError("Lost connection to Nebius API")
            return JobState(status=JobStatus.RUNNING)

        if self.behavior == "timeout_remote":
            return JobState(status=JobStatus.TIMEOUT, reason="Worker node evicted")

        if self.behavior == "failed_remote":
            return JobState(status=JobStatus.FAILED, reason="CUDA out of memory")

        if self.behavior == "cancelled_remote":
            return JobState(status=JobStatus.CANCELLED)

        # Default success: return RUNNING on first poll, COMPLETED on second
        if self._poll_count == 1:
            return JobState(status=JobStatus.RUNNING)
        return JobState(status=JobStatus.COMPLETED)

    def get_logs(self, job_id: str) -> tuple[str, str]:
        return ("stdout logs", "stderr logs")

    def get_artifacts(self, job_id: str) -> JobArtifacts:
        if self.behavior == "artifact_error":
            raise RuntimeError("Failed to download logs from S3")

        exit_code = 1 if self.behavior == "non_zero_exit" else 0
        stdout = (
            "Starting training...\n"
            '{"metrics": [{"name": "val_loss", "value": 0.123, "unit": "none"}]}'
        )
        stderr = "GPU warning: low memory bandwidth" if exit_code == 0 else "Fatal error in CUDA kernel"
        artifacts = [
            Artifact(name="model.pt", path="s3://.../model.pt", size_bytes=1024),
            Artifact(name="metrics.json", path="s3://.../metrics.json", size_bytes=256),
        ]
        return JobArtifacts(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            artifacts=artifacts,
        )

    def get_artifact_bytes(self, job_id: str, artifact_name: str) -> bytes:
        if artifact_name == "model.pt":
            return b"FAKE_PYTORCH_MODEL_WEIGHTS"
        if artifact_name == "metrics.json":
            return b'{"accuracy": 0.95}'
        return b"SOME_DATA"

    def cancel(self, job_id: str) -> None:
        self.cancelled_job_ids.append(job_id)


def test_nebius_gpu_executor_success():
    """NebiusGPUExecutor successfully runs a job, parses metrics, and persists artifacts."""
    client = FakeNebiusJobClient(behavior="success")
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalArtifactStore(root=tmp)
        executor = NebiusGPUExecutor(job_client=client, artifact_store=store)
        spec = ExperimentSpec(
            plan_id="plan_1",
            name="gpu_exp",
            description="Remote GPU experiment",
            code="print('hello')",
        )
        run = executor.execute(spec, timeout_seconds=10.0)

        assert run.status == RunStatus.COMPLETED
        assert run.exit_code == 0
        assert run.cloud_job_id == "job_nebius_12345"
        assert "Starting training" in run.stdout
        assert len(run.metrics) == 1
        assert run.metrics[0].name == "val_loss"
        assert run.metrics[0].value == 0.123

        # Check artifact persistence
        assert len(run.artifacts) == 2
        artifact_names = {a.name for a in run.artifacts}
        assert artifact_names == {"model.pt", "metrics.json"}

        # Verify content was saved in artifact store
        for art in run.artifacts:
            content = store.read(art)
            if art.name == "model.pt":
                assert content == b"FAKE_PYTORCH_MODEL_WEIGHTS"

def test_nebius_gpu_executor_artifact_persistence():
    """Remote artifacts are persisted through the ArtifactStore abstraction."""
    client = FakeNebiusJobClient(behavior="success")
    with tempfile.TemporaryDirectory() as tmp:
        store = LocalArtifactStore(root=tmp)
        executor = NebiusGPUExecutor(job_client=client, artifact_store=store)
        spec = ExperimentSpec(
            plan_id="plan_1",
            name="artifact_test",
            description="Test artifact persistence",
            code="print('hello')",
        )
        run = executor.execute(spec, timeout_seconds=10.0)

        assert run.status == RunStatus.COMPLETED
        assert len(run.artifacts) == 2

        # Verify artifacts are persisted in the store
        for artifact in run.artifacts:
            assert store.read(artifact) is not None
            if artifact.name == "model.pt":
                assert store.read(artifact) == b"FAKE_PYTORCH_MODEL_WEIGHTS"
            elif artifact.name == "metrics.json":
                assert store.read(artifact) == b'{"accuracy": 0.95}'


def test_nebius_gpu_executor_submission_failure():
    """Submission exceptions are caught and reported in the run without raising."""
    client = FakeNebiusJobClient(behavior="submit_error")
    executor = NebiusGPUExecutor(job_client=client)
    spec = ExperimentSpec(
        plan_id="plan_1",
        name="gpu_exp",
        description="Failing submission",
        code="print('hello')",
    )
    run = executor.execute(spec, timeout_seconds=10.0)

    assert run.status == RunStatus.FAILED
    assert "remote job submission failed" in run.stderr
    assert run.cloud_job_id is None
    assert run.completed_at is not None


def test_nebius_gpu_executor_polling_failure():
    """Polling exceptions are caught and reported in the run."""
    client = FakeNebiusJobClient(behavior="poll_error")
    executor = NebiusGPUExecutor(job_client=client, poll_interval=0.01)
    spec = ExperimentSpec(
        plan_id="plan_1",
        name="gpu_exp",
        description="Failing polling",
        code="print('hello')",
    )
    run = executor.execute(spec, timeout_seconds=10.0)

    assert run.status == RunStatus.FAILED
    assert "failed to poll remote job" in run.stderr
    assert run.cloud_job_id == "job_nebius_12345"


def test_nebius_gpu_executor_remote_failed():
    """Remote FAILED job status is correctly translated to RunStatus.FAILED."""
    client = FakeNebiusJobClient(behavior="failed_remote")
    executor = NebiusGPUExecutor(job_client=client, poll_interval=0.01)
    spec = ExperimentSpec(
        plan_id="plan_1",
        name="gpu_exp",
        description="Remote failure",
        code="print('hello')",
    )
    run = executor.execute(spec, timeout_seconds=10.0)

    assert run.status == RunStatus.FAILED
    assert "CUDA out of memory" in run.stderr
    assert run.cloud_job_id == "job_nebius_12345"


def test_nebius_gpu_executor_remote_timeout():
    """Remote TIMEOUT job status triggers cancellation and reports TIMEOUT."""
    client = FakeNebiusJobClient(behavior="timeout_remote")
    executor = NebiusGPUExecutor(job_client=client, poll_interval=0.01)
    spec = ExperimentSpec(
        plan_id="plan_1",
        name="gpu_exp",
        description="Remote timeout",
        code="print('hello')",
    )
    run = executor.execute(spec, timeout_seconds=10.0)

    assert run.status == RunStatus.TIMEOUT
    assert "Worker node evicted" in run.stderr
    assert "job_nebius_12345" in client.cancelled_job_ids


def test_nebius_gpu_executor_wall_clock_timeout():
    """Exceeding wall-clock timeout cancels job and returns RunStatus.TIMEOUT."""
    client = FakeNebiusJobClient(behavior="success")
    # Make get_status always return RUNNING so it loops until timeout
    class InfiniteRunningClient(FakeNebiusJobClient):
        def get_status(self, job_id: str) -> JobState:
            return JobState(status=JobStatus.RUNNING)

    inf_client = InfiniteRunningClient()
    
    # Mock time function to simulate time elapsing instantly
    current_time = 0.0
    def mock_time() -> float:
        nonlocal current_time
        current_time += 5.0
        return current_time

    executor = NebiusGPUExecutor(
        job_client=inf_client,
        poll_interval=0.01,
        time_func=mock_time,
    )
    spec = ExperimentSpec(
        plan_id="plan_1",
        name="gpu_exp",
        description="Wall clock timeout",
        code="print('hello')",
    )
    run = executor.execute(spec, timeout_seconds=2.0)

    assert run.status == RunStatus.TIMEOUT
    assert "exceeded 2.0s wall-clock timeout" in run.stderr
    assert "job_nebius_12345" in inf_client.cancelled_job_ids


def test_nebius_gpu_executor_artifact_retrieval_failure():
    """Artifact retrieval errors are captured as FAILED runs."""
    client = FakeNebiusJobClient(behavior="artifact_error")
    executor = NebiusGPUExecutor(job_client=client, poll_interval=0.01)
    spec = ExperimentSpec(
        plan_id="plan_1",
        name="gpu_exp",
        description="Artifact error",
        code="print('hello')",
    )
    run = executor.execute(spec, timeout_seconds=10.0)

    assert run.status == RunStatus.FAILED
    assert "failed to retrieve remote artifacts" in run.stderr


def test_nebius_gpu_executor_non_zero_exit():
    """Non-zero exit code on remote job sets status to FAILED."""
    client = FakeNebiusJobClient(behavior="non_zero_exit")
    executor = NebiusGPUExecutor(job_client=client, poll_interval=0.01)
    spec = ExperimentSpec(
        plan_id="plan_1",
        name="gpu_exp",
        description="Non-zero exit",
        code="print('hello')",
    )
    run = executor.execute(spec, timeout_seconds=10.0)

    assert run.status == RunStatus.FAILED
    assert run.exit_code == 1
    assert "Fatal error in CUDA kernel" in run.stderr
    assert run.metrics == []


def test_nebius_gpu_executor_implements_interface():
    """NebiusGPUExecutor must implement ExperimentExecutor interface."""
    from axiom.domain.interfaces import ExperimentExecutor
    assert issubclass(NebiusGPUExecutor, ExperimentExecutor)


def test_nebius_gpu_executor_no_local_execution(monkeypatch):
    """Ensure no subprocess or local execution happens when running NebiusGPUExecutor."""
    import subprocess
    def _raise_if_subprocess(*args, **kwargs):
        raise AssertionError("Subprocess should not be called by NebiusGPUExecutor")
    monkeypatch.setattr(subprocess, "run", _raise_if_subprocess)
    monkeypatch.setattr(subprocess, "Popen", _raise_if_subprocess)

    client = FakeNebiusJobClient(behavior="success")
    executor = NebiusGPUExecutor(job_client=client)
    spec = ExperimentSpec(
        plan_id="plan_1",
        name="no_local",
        description="No local execution",
        code="raise RuntimeError('This code must not run locally!')",
    )
    run = executor.execute(spec, timeout_seconds=10.0)
    assert run.status == RunStatus.COMPLETED


def test_nebius_gpu_executor_with_validator():
    """ExperimentValidator validates spec code statically before passing to executor."""
    from axiom.execution.validator import ExperimentValidator
    validator = ExperimentValidator()
    client = FakeNebiusJobClient(behavior="success")
    executor = NebiusGPUExecutor(job_client=client)

    # Valid code passes validation
    spec_valid = ExperimentSpec(
        plan_id="plan_1",
        name="valid",
        description="Valid code",
        code="print('hello')",
    )
    val_res = validator.validate(spec_valid)
    assert val_res.valid
    run = executor.execute(spec_valid, timeout_seconds=10.0)
    assert run.status == RunStatus.COMPLETED

    # Invalid code fails validation upstream before hitting executor
    spec_invalid = ExperimentSpec(
        plan_id="plan_1",
        name="invalid",
        description="Invalid syntax",
        code="def broken_syntax(",
    )
    val_res_inv = validator.validate(spec_invalid)
    assert not val_res_inv.valid


def test_real_nebius_job_client_init():
    """Test NebiusStorageArtifactClient initialization with settings."""
    settings = Settings(
        nebius_s3_access_key_id="test-key",
        nebius_s3_secret_access_key="test-secret",
        nebius_s3_bucket_name="my-bucket",
    )
    client = NebiusStorageArtifactClient(settings=settings)
    assert client._settings.nebius_s3_bucket_name == "my-bucket"


def test_settings_reads_s3_bucket_name_from_environment(monkeypatch):
    monkeypatch.setenv("NEBIUS_S3_BUCKET_NAME", "env-bucket")
    settings = Settings()
    assert settings.nebius_s3_bucket_name == "env-bucket"


def test_get_artifact_bytes_missing_bucket():
    """Test error raised when bucket is not configured."""
    settings = Settings(
        nebius_s3_access_key_id="test-key",
        nebius_s3_secret_access_key="test-secret",
        nebius_s3_bucket_name=None,
    )
    client = NebiusStorageArtifactClient(settings=settings)
    with pytest.raises(NebiusStorageConfigError, match="Nebius S3 bucket name not configured"):
        client.get_artifact_bytes("job-123", "metrics.json")


def test_get_artifact_bytes_success():
    """Test downloading artifact bytes with deterministic key."""
    settings = Settings(
        nebius_s3_access_key_id="test-key",
        nebius_s3_secret_access_key="test-secret",
        nebius_s3_bucket_name="my-bucket",
    )
    client = NebiusStorageArtifactClient(settings=settings)

    with patch.object(client._storage, "get_object") as mock_get_object:
        mock_get_object.return_value = b'{"metric": "accuracy", "value": 0.95}'
        content = client.get_artifact_bytes("job-123", "metrics.json")

        assert content == b'{"metric": "accuracy", "value": 0.95}'
        mock_get_object.assert_called_once_with("my-bucket", "metrics.json")


def test_integrate_nebius_artifact_retrieval_success():
    """Test successful artifact retrieval, persistence, and parsing."""
    run = ExperimentRun(
        experiment_id="exp-1",
        status=RunStatus.COMPLETED,
        stdout='{"metric": "accuracy", "value": 0.95, "unit": "%"}',
    )
    client = MagicMock(spec=NebiusStorageArtifactClient)
    client.get_artifact_bytes.return_value = b'{"metric": "accuracy", "value": 0.95, "unit": "%"}'
    client.persist_artifact.return_value = MagicMock(path="/tmp/metrics.json")

    sample = MetricSample(name="accuracy", value=0.95, unit="%")
    def mock_parse(run_obj, stdout):
        run_obj.metrics = [sample]
        return run_obj

    client.parse_and_populate_metrics.side_effect = mock_parse

    result_run = integrate_nebius_artifact_retrieval(run, "job-123", client=client)

    assert result_run.status == RunStatus.COMPLETED
    assert len(result_run.metrics) == 1
    assert result_run.metrics[0].name == "accuracy"
    assert result_run.metrics[0].value == 0.95
    client.get_artifact_bytes.assert_called_once_with("job-123", "metrics.json")
    client.persist_artifact.assert_called_once()


def test_integrate_nebius_artifact_retrieval_no_bucket():
    """Test behavior when no bucket is configured (preserves LocalExecutor behavior)."""
    run = ExperimentRun(experiment_id="exp-1", status=RunStatus.COMPLETED)
    client = MagicMock(spec=NebiusStorageArtifactClient)
    client.get_artifact_bytes.side_effect = NebiusStorageConfigError("No bucket")

    result_run = integrate_nebius_artifact_retrieval(run, "job-123", client=client)

    # LocalExecutor behavior preserved - run status unchanged, no error
    assert result_run.status == RunStatus.COMPLETED
    assert result_run.exit_code is None


def test_integrate_nebius_artifact_retrieval_not_found():
    """Test behavior when artifact is not found in storage."""
    run = ExperimentRun(experiment_id="exp-1", status=RunStatus.COMPLETED)
    client = MagicMock(spec=NebiusStorageArtifactClient)
    client.get_artifact_bytes.side_effect = NebiusStorageNotFoundError("Not found", status_code=404)

    result_run = integrate_nebius_artifact_retrieval(run, "job-123", client=client)

    assert result_run.status == RunStatus.FAILED
    assert "Not found" in result_run.stderr


def test_integrate_nebius_artifact_retrieval_auth_error():
    """Test behavior on storage authentication error."""
    run = ExperimentRun(experiment_id="exp-1", status=RunStatus.COMPLETED)
    client = MagicMock(spec=NebiusStorageArtifactClient)
    client.get_artifact_bytes.side_effect = NebiusStorageAuthError("Auth failed", status_code=401)

    result_run = integrate_nebius_artifact_retrieval(run, "job-123", client=client)

    assert result_run.status == RunStatus.FAILED
    assert "Auth failed" in result_run.stderr


def test_integrate_nebius_artifact_retrieval_storage_error():
    """Test behavior on general storage error."""
    run = ExperimentRun(experiment_id="exp-1", status=RunStatus.COMPLETED)
    client = MagicMock(spec=NebiusStorageArtifactClient)
    client.get_artifact_bytes.side_effect = NebiusStorageError("Storage error", status_code=500)

    result_run = integrate_nebius_artifact_retrieval(run, "job-123", client=client)

    assert result_run.status == RunStatus.FAILED
    assert "Storage error" in result_run.stderr



def test_integrate_handles_missing_s3_credentials_without_raising(monkeypatch):
    monkeypatch.delenv("NEBIUS_S3_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("NEBIUS_S3_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_S3_BUCKET_NAME", raising=False)
    run = ExperimentRun(experiment_id="exp-1", status=RunStatus.COMPLETED)

    result_run = integrate_nebius_artifact_retrieval(run, "job-123")

    assert result_run is run
    assert result_run.status == RunStatus.COMPLETED


def test_integrate_marks_empty_metrics_artifact_failed():
    run = ExperimentRun(experiment_id="exp-1", status=RunStatus.COMPLETED)
    client = MagicMock(spec=NebiusStorageArtifactClient)
    client.get_artifact_bytes.return_value = b'{"metrics": []}'
    client.persist_artifact.return_value = MagicMock(path="/tmp/metrics.json")

    def return_no_metrics(run_obj, content):
        run_obj.metrics = []
        return run_obj

    client.parse_and_populate_metrics.side_effect = return_no_metrics

    result_run = integrate_nebius_artifact_retrieval(run, "job-123", client=client)

    assert result_run.status == RunStatus.FAILED
    assert result_run.exit_code == -1
    assert "no valid metric samples" in result_run.stderr
