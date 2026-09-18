"""Resource limits applied to experiment subprocesses.

Best-effort, platform-aware controls. On POSIX this installs a preexec_fn
that lowers process priority and applies RLIMIT_AS / RLIMIT_CPU so runaway
experiment code cannot take down the API process. Windows gracefully degrades
to no preexec_fn.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Callable

logger = logging.getLogger("axiom.execution")

DEFAULT_MAX_CPU_SECONDS = 60.0
DEFAULT_MAX_ADDRESS_SPACE_MB = 2048


def make_preexec(
    max_cpu_seconds: float = DEFAULT_MAX_CPU_SECONDS,
    max_address_space_mb: int = DEFAULT_MAX_ADDRESS_SPACE_MB,
) -> Callable[[], None] | None:
    """Return a preexec_fn applying resource limits, or None if unsupported."""
    if sys.platform == "win32":
        return None

    import resource  # POSIX only

    def _apply() -> None:  # pragma: no cover - runs in the child process
        # Each limit is best-effort: failures (including missing platform
        # APIs) must never prevent the experiment from running.
        try:
            # Lower priority so experiment code cannot starve the API process.
            setpriority = getattr(resource, "setpriority", None)
            if setpriority is not None:
                setpriority(resource.PRIO_PROCESS, 0, 10)
        except Exception:  # noqa: BLE001 - any failure degrades gracefully
            pass
        try:
            cpu_limit = int(max_cpu_seconds)
            if cpu_limit > 0:
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
        except Exception:  # noqa: BLE001
            pass
        try:
            addr_bytes = max_address_space_mb * 1024 * 1024
            if addr_bytes > 0:
                resource.setrlimit(resource.RLIMIT_AS, (addr_bytes, addr_bytes))
        except Exception:  # noqa: BLE001
            pass

    return _apply
