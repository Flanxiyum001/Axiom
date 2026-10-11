"""Nebius GPU executor with remote artifact retrieval via Nebius Storage S3."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from axiom.config import Settings
from axiom.domain.models import Artifact, ExperimentRun, ExperimentSpec, MetricSample, RunStatus
from axiom.execution.artifacts import ArtifactStore
from axiom.execution.local_executor import LocalExecutor
from axiom.execution.metrics_protocol import parse_metrics
from axiom.execution.nebius_storage_client import (
    NebiusStorageClient,
    NebiusStorageError,
    NebiusStorageAuthError,
    NebiusStorageNotFoundError,
    NebiusStorageConfigError,
)

logger = logging.getLogger("axiom.execution")


class RealNebiusJobClient:
    """Job client that uses Nebius Storage for artifact retrieval.

    Downloads the metrics artifact from Nebius Object Storage after job completion,
    parses the metrics protocol, and populates the ExperimentRun.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._storage = NebiusStorageClient(
            access_key_id=self._settings.nebius_s3_access_key_id,
            secret_access_key=self._settings.nebius_s3_secret_access_key,
            endpoint_url=self._settings.nebius_s3_endpoint_url,
            region=self._settings.nebius_s3_region,
        )

    def get_artifact_bytes(self, job_id: str, artifact_name: str) -> bytes:
        """Download an artifact from Nebius Storage by job ID and artifact name.

        The current implementation uses the artifact name directly as the object
        key (e.g. ``metrics.json``) and does not include ``job_id`` in the key.
        The assumed mapping between a container output path and an S3 object key
        has not been verified against a live Nebius AI Cloud job.
        """
        bucket = self._settings.nebius_s3_bucket_name
        if not bucket:
            raise NebiusStorageConfigError(
                "Nebius S3 bucket name not configured. "
                "Set NEBIUS_S3_BUCKET_NAME environment variable or nebius_s3_bucket_name in settings."
            )
        key = artifact_name
        return self._storage.get_object(bucket, key)

    def persist_artifact(self, run_id: str, content: bytes, name: str = "metrics.json") -> Artifact:
        """Persist an artifact to the local ArtifactStore."""
        artifact_store = ArtifactStore()
        return artifact_store.save_output(run_id, name, content)

    def parse_and_populate_metrics(self, run: ExperimentRun, stdout: str) -> ExperimentRun:
        """Parse metrics from stdout and populate the ExperimentRun."""
        run.metrics = parse_metrics(stdout)
        return run


def integrate_nebius_artifact_retrieval(
    run: ExperimentRun,
    job_id: str,
    client: RealNebiusJobClient | None = None,
) -> ExperimentRun:
    """Integrate Nebius Storage artifact retrieval after job completion.

    After a Nebius GPU job completes, this function:
    1. Downloads the metrics artifact from Nebius Object Storage using the deterministic key: {artifact_name}
    2. Persists the downloaded file using the existing ArtifactStore
    3. Parses it using the existing AXIOM metrics protocol
    4. Populates ExperimentRun.metrics

    If storage credentials or the bucket are not configured, the run is returned unchanged.
    Missing/inaccessible artifacts or artifacts containing no valid metrics fail the run.

    Args:
        run: The ExperimentRun to update with metrics
        job_id: Remote job identifier retained for interface compatibility; the current
            object-key convention does not include a job-specific prefix.
        client: Optional RealNebiusJobClient instance (creates one from settings if not provided)

    Returns:
        The updated ExperimentRun with metrics populated if successful
    """
    try:
        # Construct lazily so missing S3 credentials are handled by the same
        # safe fallback path as a missing bucket, rather than escaping early.
        if client is None:
            client = RealNebiusJobClient()
        metrics_content = client.get_artifact_bytes(job_id, "metrics.json")
    except NebiusStorageConfigError:
        # No bucket configured - preserve existing behavior
        logger.info("Nebius Storage is not configured; leaving run unchanged")
        return run
    except NebiusStorageNotFoundError as e:
        logger.warning("Metrics artifact not found in Nebius Storage: %s", e)
        run.status = RunStatus.FAILED
        run.exit_code = -1
        run.stderr = f"Metrics artifact not found: {e}"
        return run
    except NebiusStorageAuthError as e:
        logger.error("Authentication error retrieving metrics artifact: %s", e)
        run.status = RunStatus.FAILED
        run.exit_code = -1
        run.stderr = f"Authentication error: {e}"
        return run
    except NebiusStorageError as e:
        logger.error("Error retrieving metrics artifact: %s", e)
        run.status = RunStatus.FAILED
        run.exit_code = -1
        run.stderr = f"Error retrieving metrics: {e}"
        return run

    # Persist the downloaded artifact using the existing ArtifactStore
    try:
        artifact = client.persist_artifact(run.id, metrics_content, "metrics.json")
        run.artifacts.append(artifact)
    except Exception as e:
        logger.warning("Failed to persist metrics artifact: %s", e)

    # Parse the metrics using the downloaded artifact content.
    # The artifact was downloaded from S3; parse it using the AXIOM metrics protocol.
    try:
        run = client.parse_and_populate_metrics(run, metrics_content.decode("utf-8"))
    except Exception as e:
        logger.warning("Failed to parse metrics from artifact: %s", e)
        run.status = RunStatus.FAILED
        run.exit_code = -1
        run.stderr = f"Metrics parsing error: {e}"
        return run

    if not run.metrics:
        run.status = RunStatus.FAILED
        run.exit_code = -1
        run.stderr = "Metrics artifact contained no valid metric samples"
        return run

    # Preserve cloud_job_id, status, exit code, and existing error behavior
    # (these are already set from the job execution)

    logger.info("Successfully retrieved and parsed metrics from Nebius Storage for run %s", run.id)
    return run
