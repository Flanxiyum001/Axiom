"""Metrics protocol between the experiment runner and experiment code.

Experiment code must emit a final line of JSON to stdout:

    {"metrics": [{"name": "...", "value": 1.23, "unit": "ms", "iteration": 0}]}

Everything else on stdout/stderr is preserved verbatim as raw, immutable
output. Only this protocol line is parsed into MetricSample objects, so raw
measurements always come from the experiment runner - never from an LLM.
"""

from __future__ import annotations

import json
import logging
import math

from axiom.domain.models import MetricSample

logger = logging.getLogger("axiom.execution")

METRICS_PROTOCOL_KEY = "__axiom_metrics__"
"""Recommended key inside the final JSON line emitted by experiment code."""

METRICS_DOC = """
EXPERIMENT OUTPUT PROTOCOL (required)
-------------------------------------
Your experiment code must print, as the LAST line of stdout, a single JSON
object of the form:

  {"metrics": [{"name": "<metric>", "value": <float>, "unit": "ms", "iteration": <int>}]}

Rules:
- Print progress/diagnostics freely, but the final stdout line must be the JSON.
- Metric names should match the plan's declared metrics (e.g. "latency_ms").
- Emit one entry per repetition, with iteration = 0, 1, 2, ...
- Do not fabricate values; measure them with time.perf_counter() or equivalents.
""".strip()


def parse_metrics(stdout: str) -> list[MetricSample]:
    """Extract MetricSample objects from the final JSON line of stdout.

    Returns an empty list if no protocol line is present or it is malformed.
    Raw stdout is never modified or truncated by this function.
    """
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "metrics" in payload:
            raw = payload.get("metrics")
            if not isinstance(raw, list):
                logger.warning("Metrics protocol line found but 'metrics' is not a list")
                return []
            samples: list[MetricSample] = []
            for entry in raw:
                if not isinstance(entry, dict) or "name" not in entry or "value" not in entry:
                    continue
                try:
                    value = float(entry["value"])
                    if not math.isfinite(value):
                        raise ValueError(f"non-finite metric value: {entry['value']!r}")
                    samples.append(
                        MetricSample(
                            name=str(entry["name"]),
                            value=value,
                            unit=entry.get("unit"),
                            iteration=int(entry.get("iteration", 0)),
                        )
                    )
                except (TypeError, ValueError) as exc:
                    logger.warning("Skipping malformed metric entry %s: %s", entry, exc)
            return samples
    return []
