"""Planner agent: turns hypotheses into executable experiment designs.

The planner produces an ExperimentPlan (measurement design) and an
ExperimentSpec (executable code). It proposes only; validation of results
happens in deterministic infrastructure, not here.
"""

from __future__ import annotations

import json
import logging
import re

from axiom.domain.interfaces import ReasoningProvider
from axiom.domain.models import (
    ExperimentPlan,
    ExperimentSpec,
    Hypothesis,
    ResearchObjective,
)
from axiom.providers.schemas import CodeOutput, PlanOutput

logger = logging.getLogger("axiom.agents")

KNOWN_LEVERS = ("batch_size", "threads", "precision")

PLAN_SYSTEM_PROMPT = (
    "You are the AXIOM Planner agent. Design a minimal, controlled A/B "
    "experiment for the given hypothesis: choose the variables to vary, the "
    "metrics to measure (they must include the objective's metric), and the "
    "repetition count. Respond only with JSON matching the requested schema."
)

CODE_SYSTEM_PROMPT = (
    "You are the AXIOM experiment code generator. Write a self-contained "
    "Python script implementing the planned experiment. It must honor the "
    "baseline/candidate mode from environment variables and print the metrics "
    "protocol JSON as the last stdout line. Respond only with JSON."
)


def _lever_from_statement(statement: str) -> str:
    for lever in KNOWN_LEVERS:
        if lever in statement:
            return lever
    return "batch_size"


class PlannerAgent:
    """Produces ExperimentPlan and ExperimentSpec from a Hypothesis."""

    def __init__(
        self,
        provider: ReasoningProvider,
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
        baseline_id: str | None = None,
    ) -> tuple[ExperimentPlan, ExperimentSpec]:
        """Create the plan and the executable spec for testing a hypothesis."""
        context = {
            "objective": objective.model_dump_json(),
            "hypothesis": hypothesis.model_dump_json(),
        }
        plan_output = self.provider.generate(
            system=PLAN_SYSTEM_PROMPT,
            prompt=(
                f"Hypothesis: {hypothesis.statement}\n"
                f"Objective metric: {objective.metric} "
                f"({objective.direction.value}).\n"
                "Design the experiment plan."
            ),
            context=context,
            output_type=PlanOutput,
        )
        plan = ExperimentPlan(
            hypothesis_id=hypothesis.id,
            baseline_id=baseline_id,
            variables=plan_output.variables,
            metrics=plan_output.metrics,
            repetitions=plan_output.repetitions,
            timeout_seconds=plan_output.timeout_seconds,
        )

        code_output = self.provider.generate(
            system=CODE_SYSTEM_PROMPT,
            prompt=(
                f"Experiment plan: {plan.model_dump_json()}\n"
                f"Hypothesis: {hypothesis.statement}\n"
                f"Objective metric: {objective.metric}.\n"
                "Generate the experiment code."
            ),
            context=context,
            output_type=CodeOutput,
        )

        # Pin the hypothesized lever into candidate code so baseline and
        # candidate always measure identical workloads (fair A/B).
        lever = _lever_from_statement(hypothesis.statement)
        code = EchoProviderCodePatcher.pin_lever(code_output.code, lever)

        # The plan defines the candidate condition: unless the provider set an
        # explicit mode, run the spec in candidate mode (the baseline spec is
        # created by the loop with baseline mode).
        environment = dict(code_output.environment)
        environment.setdefault("__AXIOM_LEVER_MODE__", "candidate")

        spec = ExperimentSpec(
            plan_id=plan.id,
            name=f"{hypothesis.id}-experiment",
            description=code_output.description
            or f"A/B experiment for hypothesis {hypothesis.id}",
            code=code,
            parameters=code_output.parameters,
            environment=environment,
        )
        logger.info(
            "Planner designed plan %s and spec %s for hypothesis %s (lever=%s)",
            plan.id,
            spec.id,
            hypothesis.id,
            lever,
        )
        return plan, spec


class EchoProviderCodePatcher:
    """Pins the hypothesized lever into echo-generated benchmark code.

    With a real provider this patcher becomes a validator (checking that the
    code declares its lever via AXIOM_LEVER); with the echo stub it patches
    the LEVER constant so candidate mode tunes the hypothesized mechanism.
    """

    _LEVER_ASSIGN = re.compile(r"^LEVER\s*=\s*[\"']([a-z_]+)[\"']", re.MULTILINE)

    @staticmethod
    def pin_lever(code: str, lever: str) -> str:
        patched, count = EchoProviderCodePatcher._LEVER_ASSIGN.subn(
            f'LEVER = "{lever}"', code, count=1
        )
        if count == 0:
            # Real-provider code may not contain the constant; leave untouched.
            return code
        return patched
