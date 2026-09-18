"""Filesystem artifact store.

Raw experiment outputs are immutable: artifacts are written once, content-
addressed by SHA-256, and never overwritten. Runs reference artifacts by
relative path so provenance survives across machines.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path

from axiom.domain.models import Artifact

logger = logging.getLogger("axiom.execution")


class ArtifactStore:
    """Stores run artifacts under ``<root>/<run_id>/<name>`` with SHA-256."""

    def __init__(self, root: str | Path = "artifacts") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save_output(self, run_id: str, name: str, content: bytes) -> Artifact:
        """Persist artifact bytes for a run; returns its descriptor."""
        target_dir = self.root / run_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / name
        if target.exists():
            raise FileExistsError(
                f"Artifact {target} already exists; run outputs are immutable"
            )
        target.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        logger.info("Stored artifact %s (%d bytes, sha256=%s)", target, len(content), digest)
        return Artifact(
            name=name,
            path=str(target),
            sha256=digest,
            size_bytes=len(content),
        )

    def copy_into_run(self, run_id: str, source: Path) -> Artifact:
        """Copy an existing file into a run's artifact directory."""
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(f"Cannot store missing artifact source: {source}")
        return self.save_output(run_id, source.name, source.read_bytes())

    def read(self, artifact: Artifact) -> bytes:
        """Read artifact bytes, verifying the stored SHA-256 digest."""
        data = Path(artifact.path).read_bytes()
        if artifact.sha256 and hashlib.sha256(data).hexdigest() != artifact.sha256:
            raise ValueError(
                f"Artifact integrity check failed for {artifact.path}: "
                f"expected sha256={artifact.sha256}"
            )
        return data
