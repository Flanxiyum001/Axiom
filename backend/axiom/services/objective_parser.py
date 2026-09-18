from __future__ import annotations

import re

from axiom.domain.models import Constraints, Direction, ResearchObjective


class ObjectiveParseError(ValueError):
    pass


_DECREASE_HINTS = ("reduc", "decreas", "lower", "minimiz", "cut", "faster", "less", "shrink")
_INCREASE_HINTS = ("increas", "maximiz", "higher", "more", "boost", "grow", "worsen")


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
    if metric == "latency_ms":
        direction = Direction.MAXIMIZE if any(h in lowered for h in _INCREASE_HINTS) else Direction.MINIMIZE
    else:
        direction = Direction.MINIMIZE if any(h in lowered for h in _DECREASE_HINTS) else Direction.MAXIMIZE
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    target = float(match.group(1)) if match else 20.0
    return ResearchObjective(
        description=text,
        metric=metric,
        direction=direction,
        target=target,
        constraints=Constraints(),
    )
