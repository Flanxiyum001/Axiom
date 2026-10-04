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
from axiom.domain.models import ExperimentRun, ExperimentSpec, RunStatus
from axiom.execution.artifacts import ArtifactStore
from axiom.execution.metrics_protocol import parse_metrics
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
