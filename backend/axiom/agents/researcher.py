"""Researcher agent: turns objectives into hypotheses.

Proposes only - it never executes or evaluates anything. Communication with
the reasoning provider uses typed domain objects and validated outputs.
"""

from __future__ import annotations

import json
import logging

from axiom.domain.interfaces import ReasoningProvider
from axiom.domain.models import Hypothesis, ResearchObjective

logger = logging.getLogger("axiom.agents")

SYSTEM_PROMPT = (
    "You are the AXIOM Researcher agent. Given a research objective and the "
    "history of prior hypotheses and evidence, propose exactly one new, "
    "testable hypothesis. It must state a specific system change (the lever), "
    "the expected effect on the objective's metric, and a quantitative "
    "magnitude. Respond only with JSON matching the requested schema."
)


class ResearcherAgent:
    """Proposes Hypothesis objects for a ResearchObjective."""

    def __init__(self, provider: ReasoningProvider) -> None:
        self.provider = provider

    def propose(
        self,
        objective: ResearchObjective,
        *,
        iteration: int,
        prior_evidence_summary: str = "",
    ) -> Hypothesis:
        context = {
            "objective": objective.model_dump_json(),
            "iteration": str(iteration),
            "prior_evidence": prior_evidence_summary,
        }
        hypothesis = self.provider.generate(
            system=SYSTEM_PROMPT,
            prompt=(
                f"Research objective: {objective.description}\n"
                f"Metric to improve: {objective.metric} "
                f"({objective.direction.value}; target {objective.target}% "
                f"{'better' if objective.direction.value == 'minimize' else 'larger'}). "
                f"Propose the next hypothesis."
            ),
            context=context,
            output_type=Hypothesis,
        )
        hypothesis.objective_id = objective.id
        hypothesis.iteration = iteration
        logger.info(
            "Researcher proposed hypothesis %s (iteration %d): %s",
            hypothesis.id,
            iteration,
            hypothesis.statement,
        )
        return hypothesis
