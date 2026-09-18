"""Analyst Agent: interprets evaluation evidence and produces structured analysis.

The Analyst receives:
- objective
- hypothesis
- experiment result
- deterministic evaluation result
- prior research context

It produces a structured Analysis containing:
- summary
- observations
- interpretation
- limitations
- recommended next direction

The Analyst is the bridge between raw metrics and structured research knowledge.
It is NOT the authority on experiment success — the deterministic Evaluator remains
the source of truth for whether an experiment achieved its objective.
The Analyst must NOT override evaluator results.
"""

from __future__ import annotations

import logging
from typing import Any

from ..llm.base import LLMProvider
from ..models.schemas import (
    Analysis,
    ExperimentResult,
    ResearchObjective,
)

logger = logging.getLogger("axiom.agents.analyst")

SYSTEM_PROMPT = (
    "You are the AXIOM Analyst agent. Given an experiment result, its "
    "deterministic evaluation, the research objective, and the hypothesis "
    "being tested, produce a structured analysis. You MUST NOT override "
    "the evaluator's results. The deterministic evaluation is the source "
    "of truth for whether the experiment succeeded. Your job is to interpret "
    "the evidence, not re-decide success.\n\n"
    "Produce a structured analysis with:\n"
    "- summary: A concise one-paragraph summary of the experiment and its "
    "outcome.\n"
    "- observations: A list of specific, factual observations drawn from "
    "the metrics and evaluation. Each observation must be grounded in the "
    "measured data.\n"
    "- interpretation: Your interpretation of what the evidence means. "
    "Explain whether the hypothesis was supported, what changed, and why "
    "it matters for the objective.\n"
    "- limitations: A list of limitations of this experiment or analysis. "
    "Include things like small sample size, unmeasured confounds, "
    "assumptions, or edge cases.\n"
    "- recommended_next_direction: A concrete suggestion for what to "
    "investigate or try next, based on the evidence and limitations.\n\n"
    "Respond only with JSON matching the requested schema."
)


class AnalystAgent:
    """Produces Analysis from experiment results and evaluation evidence.

    The Analyst is responsible for interpreting WHAT the evidence means.
    It never executes or evaluates anything — that is the job of the
    deterministic infrastructure.

    The Analyst must NOT override evaluator results. The deterministic
    Evaluator is the source of truth for experiment success.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def analyze(
        self,
        result: ExperimentResult,
        evaluation: Any,
        objective: ResearchObjective,
        hypothesis: Any | None = None,
        prior_context: list[Any] | None = None,
    ) -> Analysis:
        """Generate a structured Analysis from experiment results and evaluation.

        Args:
            result: The experiment result with measured metrics.
            evaluation: The deterministic evaluation result (dict or
                EvaluationResult).
            objective: The research objective being pursued.
            hypothesis: The hypothesis that was tested (optional).
            prior_context: Prior research context (memory entries,
                analyses, etc.).

        Returns:
            A validated Analysis object.
        """
        context = {
            "objective": objective.model_dump_json(),
            "experiment_result": result.model_dump_json(),
            "evaluation": (
                evaluation
                if isinstance(evaluation, dict)
                else evaluation.to_dict()
            ),
            "hypothesis": (
                hypothesis.model_dump_json() if hypothesis else None
            ),
            "prior_context": self._summarize_context(prior_context),
        }

        prompt = self._build_prompt(result, evaluation, objective, hypothesis)

        analysis = self.provider.generate(
            system=SYSTEM_PROMPT,
            prompt=prompt,
            context=context,
            output_type=Analysis,
        )

        analysis.experiment_id = result.experiment_id
        analysis.objective_id = objective.id
        if hypothesis is not None:
            analysis.hypothesis_id = hypothesis.id
            analysis.hypothesis_title = hypothesis.title

        logger.info(
            "Analyst produced analysis %s for experiment %s",
            analysis.id,
            result.experiment_id,
        )
        return analysis

    def _build_prompt(
        self,
        result: ExperimentResult,
        evaluation: Any,
        objective: ResearchObjective,
        hypothesis: Any | None,
    ) -> str:
        """Build the user prompt for analysis."""
        parts = [
            f"Objective: {objective.description}",
            f"Experiment status: {result.status}",
            "",
            "Metrics:",
        ]
        for metric in result.metrics:
            parts.append(
                f"  - {metric.name}: {metric.value} {metric.unit}"
            )

        parts.append("")
        parts.append("Deterministic Evaluation:")
        if isinstance(evaluation, dict):
            parts.append(
                f"  Success: {evaluation.get('success', 'unknown')}"
            )
            parts.append(
                f"  Constraints satisfied: "
                f"{evaluation.get('overall_constraint_satisfied', 'unknown')}"
            )
            for reasoning in evaluation.get('reasoning', []):
                parts.append(f"  - {reasoning}")
        else:
            parts.append(f"  Success: {evaluation.success}")
            parts.append(
                f"  Constraints satisfied: "
                f"{evaluation.overall_constraint_satisfied}"
            )
            for reasoning in evaluation.reasoning:
                parts.append(f"  - {reasoning}")

        if hypothesis:
            parts.append("")
            parts.append(f"Hypothesis: {hypothesis.title}")
            parts.append(f"Rationale: {hypothesis.rationale}")

        parts.append("")
        parts.append(
            "Produce a structured analysis interpreting this evidence. "
            "Remember: the deterministic evaluation is the source of truth. "
            "Do not override its results."
        )
        return "\n".join(parts)

    def _summarize_context(
        self, context: list[Any] | None
    ) -> str:
        """Summarize prior research context for the Analyst's consideration."""
        if not context:
            return "No prior research context available."
        summaries = []
        for item in context[-5:]:
            if hasattr(item, 'conclusion'):
                summaries.append(f"- {item.conclusion}")
            elif hasattr(item, 'interpretation'):
                summaries.append(f"- {item.interpretation}")
            elif isinstance(item, dict):
                fallback = item.get('interpretation', str(item))
                summaries.append(
                    f"- {item.get('conclusion', fallback)}"
                )
            else:
                summaries.append(f"- {str(item)}")
        return "\n".join(summaries) if summaries else "No prior context."