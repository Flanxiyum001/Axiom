"""Analyst agent: interprets deterministic evaluations into Evidence.

The analyst never re-decides whether an experiment succeeded - that verdict
comes from the ExperimentEvaluator. The analyst explains the measured result,
assesses confidence, and proposes what to investigate next.
"""

from __future__ import annotations

import json
import logging

from axiom.domain.interfaces import ReasoningProvider
from axiom.domain.models import Evaluation, Evidence, Hypothesis, ResearchObjective
from axiom.providers.schemas import AnalysisOutput

logger = logging.getLogger("axiom.agents")

SYSTEM_PROMPT = (
    "You are the AXIOM Analyst agent. You receive a deterministic evaluation "
    "of an experiment (deltas, improvement percent, target status computed by "
    "infrastructure - not by you). Interpret the result: state whether the "
    "hypothesis is supported, key observations, limitations, and a concise "
    "conclusion. Never contradict the measured numbers. Respond only with JSON."
)


class AnalystAgent:
    """Converts a deterministic Evaluation into Evidence."""

    def __init__(self, provider: ReasoningProvider) -> None:
        self.provider = provider

    def analyze(
        self,
        evaluation: Evaluation,
        hypothesis: Hypothesis,
        objective: ResearchObjective,
    ) -> Evidence:
        context = {
            "evaluation": evaluation.model_dump_json(),
            "hypothesis": hypothesis.model_dump_json(),
            "objective": objective.model_dump_json(),
        }
        analysis = self.provider.generate(
            system=SYSTEM_PROMPT,
            prompt=(
                f"Deterministic evaluation result: improvement_percent="
                f"{evaluation.improvement_percent}, target={evaluation.target}, "
                f"target_met={evaluation.target_met}. "
                "Provide the evidence analysis."
            ),
            context=context,
            output_type=AnalysisOutput,
        )
        evidence = Evidence(
            evaluation_id=evaluation.id,
            hypothesis_id=hypothesis.id,
            objective_id=objective.id,
            hypothesis_supported=analysis.hypothesis_supported,
            confidence=analysis.confidence,
            observations=analysis.observations,
            limitations=analysis.limitations,
            conclusion=analysis.conclusion,
        )
        logger.info(
            "Analyst produced evidence %s (supported=%s, confidence=%.2f)",
            evidence.id,
            evidence.hypothesis_supported,
            evidence.confidence,
        )
        return evidence
