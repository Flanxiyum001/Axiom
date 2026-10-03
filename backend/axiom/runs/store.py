"""Run store: persistence abstraction with a local JSON file backend."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import ValidationError

from axiom.runs.models import BenchmarkRun

logger = logging.getLogger("axiom.runs")


class RunNotFoundError(KeyError):
    """Raised when no stored run matches the requested ID."""


class RunStoreError(RuntimeError):
    """Raised when the storage backend itself fails."""


class RunStore(ABC):
    """Persistence boundary for benchmark runs, backend-agnostic."""

    @abstractmethod
    def save(self, run: BenchmarkRun) -> None:
        """Persist a run under its ID, replacing any previous snapshot."""
        raise NotImplementedError

    @abstractmethod
    def load(self, run_id: str) -> BenchmarkRun:
        """Load a run by ID, raising RunNotFoundError when absent."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, run_id: str) -> bool:
        """Check whether a run ID is stored."""
        raise NotImplementedError

    @abstractmethod
    def list_runs(self) -> list[str]:
        """List stored run IDs in sorted order."""
        raise NotImplementedError


class FileRunStore(RunStore):
    """JSON-file backend: one indented file per run, written atomically."""

    def __init__(self, root: str | Path) -> None:
        """Store runs as <root>/<run_id>.json, creating the directory."""
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, run: BenchmarkRun) -> None:
        """Serialize the run and atomically replace any previous snapshot."""
        payload = run.model_dump_json(indent=2).encode("utf-8")
        target = self._path(run.id)
        try:
            handle, staging = tempfile.mkstemp(dir=self.root, prefix=f".{run.id}-", suffix=".tmp")
            try:
                with os.fdopen(handle, "wb") as file:
                    file.write(payload)
                os.replace(staging, target)
            except BaseException:
                try:
                    os.unlink(staging)
                except OSError:
                    pass
                raise
        except OSError as exc:
            raise RunStoreError(f"Cannot save run {run.id!r}: {exc}") from exc

    def load(self, run_id: str) -> BenchmarkRun:
        """Read and validate a stored run, with clear errors for all failures."""
        target = self._path(run_id)
        try:
            text = target.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise RunNotFoundError(f"No stored run {run_id!r}") from exc
        except OSError as exc:
            raise RunStoreError(f"Cannot read run {run_id!r}: {exc}") from exc
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RunStoreError(f"Stored run {run_id!r} is not valid JSON: {exc}") from exc
        try:
            return BenchmarkRun.model_validate(data)
        except ValidationError as exc:
            raise RunStoreError(f"Stored run {run_id!r} failed validation: {exc}") from exc

    def exists(self, run_id: str) -> bool:
        """Check for the run file without reading it."""
        return self._path(run_id).is_file()

    def list_runs(self) -> list[str]:
        """Sorted IDs of valid stored runs, skipping foreign files."""
        try:
            candidates = [path for path in self.root.glob("*.json") if path.is_file()]
        except OSError as exc:
            raise RunStoreError(f"Cannot list runs in {self.root}: {exc}") from exc
        valid: list[str] = []
        for path in candidates:
            try:
                payload = path.read_bytes()
            except OSError as exc:
                raise RunStoreError(f"Cannot read {path.name}: {exc}") from exc
            try:
                run = BenchmarkRun.model_validate_json(payload)
            except Exception as exc:  # noqa: BLE001 - foreign files are skipped loudly
                logger.warning("Skipping non-run file %s: %s", path.name, exc)
                continue
            if run.id != path.stem:
                logger.warning(
                    "Skipping %s: stored id %r does not match filename", path.name, run.id
                )
                continue
            valid.append(path.stem)
        return sorted(valid)

    def _path(self, run_id: str) -> Path:
        """Resolve the file for a run ID, rejecting path escapes."""
        if not run_id or run_id in (".", "..") or "/" in run_id or "\\" in run_id or "\x00" in run_id:
            raise ValueError(f"Invalid run ID: {run_id!r}")
        return self.root / f"{run_id}.json"
