"""Tests for Nebius GPU Executor with remote artifact retrieval."""

from unittest.mock import MagicMock, patch
import pytest

from axiom.config import Settings
from axiom.domain.models import ExperimentRun, MetricSample, RunStatus
from axiom.execution.nebius_gpu_executor import (
    RealNebiusJobClient,
    integrate_nebius_artifact_retrieval,
)
from axiom.execution.nebius_storage_client import (
    NebiusStorageError,
    NebiusStorageAuthError,
    NebiusStorageNotFoundError,
    NebiusStorageConfigError,
)


def test_real_nebius_job_client_init():
    """Test RealNebiusJobClient initialization with settings."""
    settings = Settings(
        nebius_s3_access_key_id="test-key",
        nebius_s3_secret_access_key="test-secret",
        nebius_s3_bucket_name="my-bucket",
    )
    client = RealNebiusJobClient(settings=settings)
    assert client._settings.nebius_s3_bucket_name == "my-bucket"


def test_get_artifact_bytes_missing_bucket():
    """Test error raised when bucket is not configured."""
    settings = Settings(
        nebius_s3_access_key_id="test-key",
        nebius_s3_secret_access_key="test-secret",
        nebius_s3_bucket_name=None,
    )
    client = RealNebiusJobClient(settings=settings)
    with pytest.raises(NebiusStorageConfigError, match="Nebius S3 bucket name not configured"):
        client.get_artifact_bytes("job-123", "metrics.json")


def test_get_artifact_bytes_success():
    """Test downloading artifact bytes with deterministic key."""
    settings = Settings(
        nebius_s3_access_key_id="test-key",
        nebius_s3_secret_access_key="test-secret",
        nebius_s3_bucket_name="my-bucket",
    )
    client = RealNebiusJobClient(settings=settings)

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
    client = MagicMock(spec=RealNebiusJobClient)
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
    client = MagicMock(spec=RealNebiusJobClient)
    client.get_artifact_bytes.side_effect = NebiusStorageConfigError("No bucket")

    result_run = integrate_nebius_artifact_retrieval(run, "job-123", client=client)

    # LocalExecutor behavior preserved - run status unchanged, no error
    assert result_run.status == RunStatus.COMPLETED
    assert result_run.exit_code is None


def test_integrate_nebius_artifact_retrieval_not_found():
    """Test behavior when artifact is not found in storage."""
    run = ExperimentRun(experiment_id="exp-1", status=RunStatus.COMPLETED)
    client = MagicMock(spec=RealNebiusJobClient)
    client.get_artifact_bytes.side_effect = NebiusStorageNotFoundError("Not found", status_code=404)

    result_run = integrate_nebius_artifact_retrieval(run, "job-123", client=client)

    assert result_run.status == RunStatus.FAILED
    assert "Not found" in result_run.stderr


def test_integrate_nebius_artifact_retrieval_auth_error():
    """Test behavior on storage authentication error."""
    run = ExperimentRun(experiment_id="exp-1", status=RunStatus.COMPLETED)
    client = MagicMock(spec=RealNebiusJobClient)
    client.get_artifact_bytes.side_effect = NebiusStorageAuthError("Auth failed", status_code=401)

    result_run = integrate_nebius_artifact_retrieval(run, "job-123", client=client)

    assert result_run.status == RunStatus.FAILED
    assert "Auth failed" in result_run.stderr


def test_integrate_nebius_artifact_retrieval_storage_error():
    """Test behavior on general storage error."""
    run = ExperimentRun(experiment_id="exp-1", status=RunStatus.COMPLETED)
    client = MagicMock(spec=RealNebiusJobClient)
    client.get_artifact_bytes.side_effect = NebiusStorageError("Storage error", status_code=500)

    result_run = integrate_nebius_artifact_retrieval(run, "job-123", client=client)

    assert result_run.status == RunStatus.FAILED
    assert "Storage error" in result_run.stderr
