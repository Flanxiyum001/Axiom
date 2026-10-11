"""Nebius job-client abstraction for remote GPU execution.

This module defines the smallest clean interface that ``NebiusGPUExecutor``
depends on to submit, monitor and retrieve results from a remote GPU job.

The production Nebius API client will be implemented later as a concrete
subclass.  For local testing, a deterministic fake client lives in
``tests/test_nebius_gpu_executor.py``.

The abstraction is intentionally minimal:

- ``submit`` – enqueue a remote job and receive a job identifier.
- ``get_status`` – query the current lifecycle state of a job.
- ``get_logs`` – retrieve accumulated stdout/stderr.
- ``get_artifacts`` – retrieve output artifacts produced by the job.
- ``cancel`` – best-effort cancellation of a running job.

No HTTP, SDK or authentication logic belongs here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from axiom.domain.models import Artifact, ExperimentSpec


class JobStatus(str, Enum):
    """Lifecycle states reported by a remote job client."""

    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class JobHandle:
    """Opaque reference to a submitted remote job."""

    job_id: str
    submitted_at: float | None = None
    spec_id: str | None = None


@dataclass
class JobState:
    """Snapshot of a remote job's current state."""

    status: JobStatus
    exit_code: int | None = None
    reason: str = ""
    """Optional human-readable reason (e.g. failure message)."""


@dataclass
class JobArtifacts:
    """Collected outputs from a finished remote job."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    artifacts: list[Artifact] = field(default_factory=list)


class NebiusJobClient(ABC):
    """Abstraction over a remote GPU job submission/monitoring system.

    Implementations must NOT raise for expected remote failures; they
    should surface them through :class:`JobState` so the executor can
    translate them into ``ExperimentRun`` outcomes.
    """

    @abstractmethod
    def submit(self, spec: ExperimentSpec, **kwargs: object) -> JobHandle:
        """Submit ``spec`` for remote execution and return a handle."""
        raise NotImplementedError

    @abstractmethod
    def get_status(self, job_id: str) -> JobState:
        """Return the current :class:`JobState` for ``job_id``."""
        raise NotImplementedError

    @abstractmethod
    def get_logs(self, job_id: str) -> tuple[str, str]:
        """Return ``(stdout, stderr)`` accumulated for ``job_id``."""
        raise NotImplementedError

    @abstractmethod
    def get_artifacts(self, job_id: str) -> JobArtifacts:
        """Return collected artifacts, logs and exit code for ``job_id``."""
        raise NotImplementedError

    @abstractmethod
    def cancel(self, job_id: str) -> None:
        """Best-effort cancellation of a remote job."""
        raise NotImplementedError

    @abstractmethod
    def get_artifact_bytes(self, job_id: str, artifact_name: str) -> bytes:
        """Download the raw bytes of a specific artifact by name."""
        raise NotImplementedError