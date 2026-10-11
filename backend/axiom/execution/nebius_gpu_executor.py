"""Nebius GPU executor: runs ExperimentSpecs on a remote GPU via a job client.

This executor does NOT execute experiment code locally.  It delegates every
runtime concern to a NebiusJobClient abstraction, which keeps the executor
testable without any network or GPU access.  The production Nebius API client
will be a thin concrete subclass of NebiusJobClient.

The executor preserves the full ExperimentExecutor contract:

- Failures (submission, polling, artifact retrieval, remote FAILED/TIMEOUT)
  are captured inside the returned ExperimentRun rather than raised.
- Metrics are parsed using the existing metrics_protocol so the format is
  identical to LocalExecutor.
- Artifacts are persisted through the existing ArtifactStore abstraction.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Callable

from axiom.domain.interfaces import ExperimentExecutor
from axiom.config import Settings
from axiom.domain.models import Artifact, ExperimentRun, ExperimentSpec, RunStatus
from axiom.execution.artifacts import ArtifactStore
from axiom.execution.metrics_protocol import parse_metrics
from axiom.execution.nebius_storage_client import (
    NebiusStorageClient,
    NebiusStorageError,
    NebiusStorageAuthError,
    NebiusStorageNotFoundError,
    NebiusStorageConfigError,
)
from axiom.execution.nebius_job_client import (
    JobArtifacts,
    JobHandle,
    JobStatus,
    NebiusJobClient,
)

logger = logging.getLogger("axiom.execution")


class NebiusGPUExecutor(ExperimentExecutor):
    """Executes ExperimentSpecs on a remote GPU via a job-client abstraction."""

    def __init__(
        self,
        job_client: NebiusJobClient,
        artifact_store: ArtifactStore | None = None,
        *,
        poll_interval: float = 1.0,
        time_func: Callable[[], float] = time.monotonic,
    ) -> None:
        self.job_client = job_client
        self.artifact_store = artifact_store
        self.poll_interval = max(0.01, float(poll_interval))
        self.time_func = time_func

    def execute(self, spec: ExperimentSpec, timeout_seconds: float) -> ExperimentRun:
        run = ExperimentRun(
            experiment_id=spec.id,
            status=RunStatus.PENDING,
        )
        started = self.time_func()
        run.started_at = datetime.now(UTC)

        # 1. Submit the remote job.
        try:
            handle = self.job_client.submit(spec)
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.stderr = f"[axiom] remote job submission failed: {exc}"
            run.completed_at = datetime.now(UTC)
            logger.warning("Submission failed for spec %s: %s", spec.id, exc)
            return run

        run.cloud_job_id = handle.job_id

        # 2. Poll until terminal state or wall-clock timeout.
        deadline = started + timeout_seconds
        while True:
            now = self.time_func()
            if now >= deadline:
                run.status = RunStatus.TIMEOUT
                run.stderr = (
                    f"[axiom] remote job {handle.job_id} exceeded "
                    f"{timeout_seconds}s wall-clock timeout"
                )
                run.completed_at = datetime.now(UTC)
                self._best_effort_cancel(handle.job_id)
                logger.warning(
                    "Remote job %s timed out after %.2fs",
                    handle.job_id,
                    timeout_seconds,
                )
                return run

            try:
                state = self.job_client.get_status(handle.job_id)
            except Exception as exc:
                run.status = RunStatus.FAILED
                run.stderr = (
                    f"[axiom] failed to poll remote job {handle.job_id}: {exc}"
                )
                run.completed_at = datetime.now(UTC)
                logger.warning("Polling failed for job %s: %s", handle.job_id, exc)
                return run

            if state.status == JobStatus.COMPLETED:
                break
            if state.status == JobStatus.FAILED:
                run.status = RunStatus.FAILED
                run.stderr = (
                    f"[axiom] remote job {handle.job_id} failed: "
                    f"{state.reason}".strip()
                )
                run.completed_at = datetime.now(UTC)
                logger.warning(
                    "Remote job %s failed: %s", handle.job_id, state.reason
                )
                return run
            if state.status == JobStatus.TIMEOUT:
                run.status = RunStatus.TIMEOUT
                run.stderr = (
                    f"[axiom] remote job {handle.job_id} timed out: "
                    f"{state.reason}".strip()
                )
                run.completed_at = datetime.now(UTC)
                self._best_effort_cancel(handle.job_id)
                logger.warning("Remote job %s reported timeout", handle.job_id)
                return run
            if state.status == JobStatus.CANCELLED:
                run.status = RunStatus.FAILED
                run.stderr = (
                    f"[axiom] remote job {handle.job_id} was cancelled"
                )
                run.completed_at = datetime.now(UTC)
                logger.warning("Remote job %s was cancelled", handle.job_id)
                return run

            time.sleep(self.poll_interval)

        # 3. Retrieve logs, exit code and artifacts.
        try:
            job_artifacts = self.job_client.get_artifacts(handle.job_id)
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.stderr = (
                f"[axiom] failed to retrieve remote artifacts for "
                f"{handle.job_id}: {exc}"
            )
            run.completed_at = datetime.now(UTC)
            logger.warning(
                "Artifact retrieval failed for job %s: %s", handle.job_id, exc
            )
            return run

        run.exit_code = job_artifacts.exit_code
        run.stdout = job_artifacts.stdout
        run.stderr = job_artifacts.stderr
        run.status = (
            RunStatus.COMPLETED
            if (job_artifacts.exit_code or 0) == 0
            else RunStatus.FAILED
        )

        # 4. Parse metrics using the EXISTING metrics protocol.
        if run.status == RunStatus.COMPLETED:
            run.metrics = parse_metrics(run.stdout)
        else:
            run.metrics = []

        # 5. Persist remote artifacts through the existing ArtifactStore.
        if self.artifact_store is not None:
            for artifact in job_artifacts.artifacts:
                try:
                    content = self.job_client.get_artifact_bytes(
                        handle.job_id, artifact.name
                    )
                    persisted = self.artifact_store.save_output(
                        run.id, artifact.name, content
                    )
                    run.artifacts.append(persisted)
                except Exception:
                    logger.exception(
                        "Failed to persist remote artifact %s for run %s",
                        artifact.name,
                        run.id,
                    )

        run.completed_at = datetime.now(UTC)
        logger.info(
            "Remote run %s (job %s) finished: status=%s exit=%s",
            run.id,
            handle.job_id,
            run.status.value,
            run.exit_code,
        )
        return run

    def _best_effort_cancel(self, job_id: str) -> None:
        """Swallow cancellation errors - we are already timing out."""
        try:
            self.job_client.cancel(job_id)
        except Exception:
            logger.debug("Cancel failed for job %s", job_id, exc_info=True)


class NebiusStorageArtifactClient:
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
    client: NebiusStorageArtifactClient | None = None,
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
        client: Optional NebiusStorageArtifactClient instance (creates one from settings if not provided)

    Returns:
        The updated ExperimentRun with metrics populated if successful
    """
    try:
        # Construct lazily so missing S3 credentials are handled by the same
        # safe fallback path as a missing bucket, rather than escaping early.
        if client is None:
            client = NebiusStorageArtifactClient()
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
