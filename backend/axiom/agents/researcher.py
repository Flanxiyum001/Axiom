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
    "You are the AXIOM Researcher agent. Given a research objective and prior evidence, "
    "propose exactly one new, testable hypothesis. "
    "You must return ONLY valid JSON matching the Hypothesis schema, with these exact fields:\n"
    "- objective_id: (string UUID matching the objective)\n"
    "- statement: specific system change (the lever)\n"
    "- rationale: explanation of why the hypothesis is plausible\n"
    "- expected_effect: a nested object containing:\n"
    "  - metric: must match the objective metric\n"
    "  - direction: must match the objective direction ('minimize' or 'maximize')\n"
    "  - magnitude_percent: quantitative expected relative change in percent (float)\n"
    "  - rationale: brief explanation of expected effect\n"
    "Respond only with JSON."
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
