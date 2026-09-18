from __future__ import annotations

import re

from axiom.domain.models import Constraints, Direction, ResearchObjective


class ObjectiveParseError(ValueError):
    pass


_MINIMIZE_HINTS = ("reduc", "decreas", "lower", "minimiz", "cut", "faster", "less")
_MAXIMIZE_HINTS = ("increas", "improv", "boost", "maximiz", "higher", "more")


def parse_objective(description: str) -> ResearchObjective:
    text = description.strip()
    if len(text) < 3:
        raise ObjectiveParseError("Objective description must be at least 3 characters")
    lowered = text.lower()
    if "latency" in lowered:
        metric = "latency_ms"
    elif "throughput" in lowered:
        metric = "throughput"
    elif "accuracy" in lowered:
        metric = "accuracy"
    else:
        metric = "latency_ms"
    if any(h in lowered for h in _MINIMIZE_HINTS):
        direction = Direction.MINIMIZE
    elif any(h in lowered for h in _MAXIMIZE_HINTS):
        direction = Direction.MAXIMIZE
    elif metric == "throughput":
        direction = Direction.MAXIMIZE
    else:
        direction = Direction.MINIMIZE
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    target = float(match.group(1)) if match else 20.0
    return ResearchObjective(
        description=text,
        metric=metric,
        direction=direction,
        target=target,
        constraints=Constraints(),
    )
