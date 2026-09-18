"""Planner Agent: turns hypotheses into executable experiment plans.

The Planner receives:
- ResearchObjective
- Hypothesis
- available experiment types / registry

It produces a validated ExperimentPlan.

CRITICAL SAFETY RULE:
The Planner cannot invent arbitrary executable code.
It must select an experiment from the approved experiment registry.

The plan should contain:
- experiment type
- parameters
- metrics to collect
- success criteria
- rationale

If the requested experiment type does not exist in the registry, reject it.
"""

from __future__ import annotations

import logging
from typing import Any

from ..llm.base import LLMProvider, ProviderError
from ..models.schemas import ExperimentPlan, Hypothesis, ResearchObjective

logger = logging.getLogger("axiom.agents.planner")

SYSTEM_PROMPT = (
    "You are the AXIOM Planner agent. Design a minimal, controlled A/B "
    "experiment for the given hypothesis: choose the variables to vary, the "
    "metrics to measure (they must include the objective's metric), and the "
    "repetition count. Respond only with JSON matching the requested schema. "
    "You MUST select an experiment type from the provided approved registry."
)


class PlannerAgent:
    """Produces ExperimentPlan from a Hypothesis.

    The planner is responsible for deciding HOW to structure a valid experiment.
    It never executes or evaluates anything - that is the job of the
    deterministic infrastructure.

    CRITICAL: The planner can only select experiment types from the approved
    registry. It cannot invent arbitrary executable code.
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        default_repetitions: int = 3,
        default_timeout_seconds: float = 60.0,
    ) -> None:
        self.provider = provider
        self.default_repetitions = default_repetitions
        self.default_timeout_seconds = default_timeout_seconds

    def design(
        self,
        hypothesis: Hypothesis,
        objective: ResearchObjective,
        *,
        available_experiments: list[str] | None = None,
        baseline_id: str | None = None,
    ) -> ExperimentPlan:
        """Create an experiment plan for testing a hypothesis."""
        if available_experiments is None:
            available_experiments = self._get_default_registry()

        context = {
            "objective": objective.model_dump_json(),
            "hypothesis": hypothesis.model_dump_json(),
            "available_experiments": ", ".join(available_experiments),
        }

        prompt = self._build_prompt(
            hypothesis, objective, available_experiments
        )

        plan = self.provider.generate(
            system=SYSTEM_PROMPT,
            prompt=prompt,
            context=context,
            output_type=ExperimentPlan,
        )

        # CRITICAL SAFETY RULE: Validate that the experiment type exists
        self._validate_experiment_type(plan.title, available_experiments)

        # Ensure the plan has required fields
        plan.hypothesis_id = hypothesis.id
        if not plan.metrics:
            plan.metrics = [m.name for m in objective.metrics]
        if not plan.success_criteria:
            plan.success_criteria = (
                f"Achieve {objective.target} improvement in "
                f"{objective.metrics[0].name if objective.metrics else 'primary metric'}"
            )

        logger.info(
            "Planner designed plan %s for hypothesis %s (experiment_type=%s)",
            plan.id,
            hypothesis.id,
            plan.title,
        )
        return plan

    def _build_prompt(
        self,
        hypothesis: Hypothesis,
        objective: ResearchObjective,
        available_experiments: list[str],
    ) -> str:
        """Build the user prompt for experiment planning."""
        parts = [
            f"Hypothesis: {hypothesis.title}",
            f"Description: {hypothesis.description}",
            f"Rationale: {hypothesis.rationale}",
            f"Expected outcome: {hypothesis.expected_outcome}",
            "",
            f"Objective metric: {objective.metrics[0].name if objective.metrics else 'unknown'}",
            f"Objective direction: {objective.metrics[0].direction.value if objective.metrics else 'unknown'}",
            f"Objective target: {objective.target}",
            "",
            f"Approved experiment types: {', '.join(available_experiments)}",
            "",
            "Design the experiment plan. You MUST select an experiment type "
            "from the approved list above.",
        ]
        return "\n".join(parts)

    def _validate_experiment_type(
        self,
        experiment_type: str,
        available_experiments: list[str],
    ) -> None:
        """Validate that the experiment type exists in the approved registry.

        CRITICAL SAFETY RULE: The planner cannot invent arbitrary executable
        code. It must select from the approved experiment registry.

        Args:
            experiment_type: The experiment type name from the plan.
            available_experiments: List of approved experiment type names.

        Raises:
            ValueError: If the experiment type is not in the registry.
        """
        if experiment_type not in available_experiments:
            raise ValueError(
                f"Experiment type '{experiment_type}' is not in the approved "
                f"registry. Available types: {available_experiments}"
            )

    def _get_default_registry(self) -> list[str]:
        """Get the default list of approved experiment types.

        Returns:
            List of approved experiment type names.
        """
        return [
            "baseline_benchmark",
            "fp16_optimization",
            "batch_size_optimization",
        ]