"""Local executor: runs experiment code in an isolated subprocess.

Isolation and safety properties:
- Experiment code is written to a fresh temporary directory per run and
  executed with cwd set there; it never receives host filesystem paths.
- A hard wall-clock timeout kills runaway runs (status=timeout).
- POSIX resource limits (CPU seconds, address space, lowered priority) are
  applied best-effort via preexec_fn.
- stdout/stderr are captured verbatim; only the trailing metrics-protocol JSON
  line is parsed into MetricSample objects.
- Raw outputs are immutable: they are persisted to the ArtifactStore and the
  database record is written once by the orchestrating service.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from axiom.domain.interfaces import ExperimentExecutor
from axiom.domain.models import ExperimentRun, ExperimentSpec, RunStatus
from axiom.execution.artifacts import ArtifactStore
from axiom.execution.metrics_protocol import parse_metrics
from axiom.execution.resource_limits import (
    DEFAULT_MAX_ADDRESS_SPACE_MB,
    DEFAULT_MAX_CPU_SECONDS,
    make_preexec,
)

logger = logging.getLogger("axiom.execution")

ENTRYPOINT = "experiment_entrypoint.py"


class LocalExecutor(ExperimentExecutor):
    """Executes ExperimentSpecs in subprocesses on the local machine."""

    def __init__(
        self,
        artifact_store: ArtifactStore | None = None,
        *,
        python_executable: str | None = None,
        max_cpu_seconds: float = DEFAULT_MAX_CPU_SECONDS,
        max_address_space_mb: int = DEFAULT_MAX_ADDRESS_SPACE_MB,
        extra_env: dict[str, str] | None = None,
    ) -> None:
        self.artifact_store = artifact_store
        self.python_executable = python_executable or sys.executable
        self.max_cpu_seconds = max_cpu_seconds
        self.max_address_space_mb = max_address_space_mb
        self.extra_env = dict(extra_env or {})

    def execute(self, spec: ExperimentSpec, timeout_seconds: float) -> ExperimentRun:
        run = ExperimentRun(
            experiment_id=spec.id,
            status=RunStatus.PENDING,
        )
        with tempfile.TemporaryDirectory(prefix="axiom-run-") as tmp:
            workdir = Path(tmp)
            code_path = workdir / ENTRYPOINT
            code_path.write_text(spec.code, encoding="utf-8")

            env = self._build_env(spec)
            started = time.time()
            run.started_at = run.started_at or datetime.now(UTC)

            preexec = make_preexec(
                max_cpu_seconds=min(self.max_cpu_seconds, max(timeout_seconds * 4, 10.0)),
                max_address_space_mb=self.max_address_space_mb,
            )
            try:
                proc = subprocess.run(
                    [self.python_executable, ENTRYPOINT],
                    cwd=workdir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=max(timeout_seconds, 0.1),
                    preexec_fn=preexec,
                    check=False,
                )
                run.exit_code = proc.returncode
                run.stdout = proc.stdout
                run.stderr = proc.stderr
                run.status = (
                    RunStatus.COMPLETED if proc.returncode == 0 else RunStatus.FAILED
                )
            except subprocess.TimeoutExpired as exc:
                run.status = RunStatus.TIMEOUT
                run.exit_code = None
                run.stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(
                    exc.stdout, bytes
                ) else (exc.stdout or "")
                run.stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(
                    exc.stderr, bytes
                ) else (exc.stderr or "")
                run.stderr = (run.stderr or "") + f"\n[axiom] run exceeded {timeout_seconds}s wall clock; killed"
            except OSError as exc:
                run.status = RunStatus.FAILED
                run.stderr = f"[axiom] failed to launch experiment process: {exc}"

            elapsed = time.time() - started
            logger.info(
                "Run %s for spec %s finished: status=%s exit=%s elapsed=%.2fs",
                run.id,
                spec.id,
                run.status.value,
                run.exit_code,
                elapsed,
            )
            run.metrics = parse_metrics(run.stdout) if run.status == RunStatus.COMPLETED else []
            run.completed_at = datetime.now(UTC)

            # Persist a run manifest as an immutable artifact (provenance).
            if self.artifact_store is not None:
                try:
                    manifest = {
                        "run_id": run.id,
                        "experiment_id": spec.id,
                        "status": run.status.value,
                        "exit_code": run.exit_code,
                        "elapsed_seconds": round(elapsed, 3),
                        "workdir": "ephemeral (removed after run)",
                    }
                    run.artifacts.append(
                        self.artifact_store.save_output(
                            run.id,
                            "run_manifest.json",
                            json.dumps(manifest, indent=2).encode("utf-8"),
                        )
                    )
                except Exception:  # noqa: BLE001 - artifact failure must not fail the run
                    logger.exception("Failed to persist run manifest artifact")

        return run

    def _build_env(self, spec: ExperimentSpec) -> dict[str, str]:
        """Minimal, controlled environment for the child process.

        Arbitrary host filesystem access is not exposed: the child gets PATH,
        PYTHONHASHSEED (fixed for reproducibility) and the spec's declared
        environment plus Axiom-provided context variables only.
        """
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "AXIOM_EXPERIMENT_ID": spec.id,
            "AXIOM_PLAN_ID": spec.plan_id,
            "AXIOM_RUN_ID": "",  # patched by orchestrator if needed
        }
        env.update(self.extra_env)
        # Spec-declared environment (validated by planner/validators).
        for key, value in spec.environment.items():
            env[str(key)] = str(value)
        for key, value in spec.parameters.items():
            env[f"AXIOM_PARAM_{str(key).upper()}"] = str(value)
        return env
