"""Researcher Agent: generates hypotheses from research objectives and history.

The Researcher Agent answers conceptually: "What should AXIOM investigate next?"

It receives:
- ResearchObjective
- previous hypotheses
- previous experiment results
- evaluation evidence
- memory/context

It produces a validated Hypothesis.

The LLM decides:
- what to investigate
- why it might work
- how to structure a valid experiment
- what the observed evidence means
- what to try next

The deterministic system decides:
- whether an experiment is allowed
- how it executes
- what metrics are produced
- whether constraints are satisfied
- whether the objective is actually achieved
"""

from __future__ import annotations

import logging
from typing import Any

from ..llm.base import LLMProvider, ProviderError
from ..models.schemas import Hypothesis, ResearchObjective

logger = logging.getLogger("axiom.agents.researcher")

SYSTEM_PROMPT = (
    "You are the AXIOM Researcher agent. Given a research objective and the "
    "history of prior hypotheses and evidence, propose exactly one new, "
    "testable hypothesis. It must state a specific system change (the lever), "
    "the expected effect on the objective's metric, and a quantitative "
    "magnitude. Respond only with JSON matching the requested schema."
)


class ResearcherAgent:
    """Proposes Hypothesis objects for a ResearchObjective.

    The researcher is responsible for deciding WHAT to investigate next.
    It never executes or evaluates anything - that is the job of the
    deterministic infrastructure.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def propose(
        self,
        objective: ResearchObjective,
        *,
        iteration: int = 0,
        prior_hypotheses: list[Hypothesis] | None = None,
        prior_results: list[Any] | None = None,
        prior_evidence: list[Any] | None = None,
        memory_context: dict[str, Any] | None = None,
    ) -> Hypothesis:
        """Generate a validated hypothesis for the given research objective."""
        context = {
            "objective": objective.model_dump_json(),
            "iteration": str(iteration),
            "prior_evidence": self._summarize_evidence(prior_evidence),
            "prior_results": self._summarize_results(prior_results),
            "prior_hypotheses": self._summarize_hypotheses(prior_hypotheses),
            "memory_context": str(memory_context or {}),
        }

        prompt = self._build_prompt(
            objective, iteration, prior_hypotheses, prior_results
        )

        hypothesis = self.provider.generate(
            system=SYSTEM_PROMPT,
            prompt=prompt,
            context=context,
            output_type=Hypothesis,
        )

        hypothesis.objective_id = objective.id

        logger.info(
            "Researcher proposed hypothesis (iteration %d): %s",
            iteration,
            hypothesis.title,
        )
        return hypothesis

    def _build_prompt(
        self,
        objective: ResearchObjective,
        iteration: int,
        prior_hypotheses: list[Hypothesis] | None,
        prior_results: list[Any] | None,
    ) -> str:
        """Build the user prompt for hypothesis generation."""
        parts = [
            f"Research objective: {objective.description}",
            f"Iteration: {iteration}",
        ]

        if objective.metrics:
            metric = objective.metrics[0]
            parts.append(
                f"Metric to improve: {metric.name} ({metric.direction.value})"
            )
            parts.append(f"Target: {objective.target}")

        if prior_hypotheses:
            parts.append("\nPrevious hypotheses tested:")
            for h in prior_hypotheses[-5:]:
                parts.append(f"  - {h.title}: {h.description}")

        if prior_results:
            parts.append("\nPrevious results:")
            for r in prior_results[-5:]:
                parts.append(f"  - {r}")

        parts.append("\nPropose the next hypothesis.")
        return "\n".join(parts)

    def _summarize_evidence(self, evidence: list[Any] | None) -> str:
        """Summarize prior evaluation evidence for context."""
        if not evidence:
            return "No prior evidence available."
        summaries = []
        for e in evidence[-5:]:
            if hasattr(e, "conclusion"):
                summaries.append(f"- {e.conclusion}")
            elif isinstance(e, dict):
                summaries.append(f"- {e.get('conclusion', str(e))}")
            else:
                summaries.append(f"- {str(e)}")
        return "\n".join(summaries) if summaries else "No prior evidence."

    def _summarize_results(self, results: list[Any] | None) -> str:
        """Summarize prior experiment results for context."""
        if not results:
            return "No prior results available."
        summaries = []
        for r in results[-5:]:
            if hasattr(r, "status"):
                summaries.append(f"- Status: {r.status}")
            elif isinstance(r, dict):
                summaries.append(f"- Status: {r.get('status', str(r))}")
            else:
                summaries.append(f"- {str(r)}")
        return "\n".join(summaries) if summaries else "No prior results."

    def _summarize_hypotheses(self, hypotheses: list[Hypothesis] | None) -> str:
        """Summarize prior hypotheses for context."""
        if not hypotheses:
            return "No prior hypotheses."
        return "\n".join(f"- {h.title}" for h in hypotheses[-5:])