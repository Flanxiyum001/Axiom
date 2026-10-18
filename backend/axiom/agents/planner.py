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
from axiom.providers.echo_provider import EchoReasoningProvider

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
    "Python script implementing the planned experiment. "
    "CRITICAL: Use only standard library modules (os, json, time, random, statistics, math). "
    "Do NOT import torch, tensorflow, or any external ML library. "
    "Simulate the model inference using simple arithmetic or random number generation. "
    "The script must read the mode from the environment variable EXPERIMENT_MODE "
    "(set to 'baseline' or 'candidate'). "
    "It must print, as the LAST line of stdout, a single JSON object with a "
    '"metrics" key containing a list of metric entries. Each entry must have '
    '"name" (e.g. "latency_ms"), "value" (a float), and optionally '
    '"unit" and "iteration". Example: {"metrics": [{"name": "latency_ms", '
    '"value": 95.5, "unit": "ms", "iteration": 0}]}. '
    "Always include the objective metric in your output. "
    "Respond only with JSON."
)


def _normalize_code(code: str) -> str:
    """Safely normalizes escape sequences in LLM-generated code.

    LLMs returning JSON often escape newlines and quotes as literal escape sequences
    (\\n, \\t, \\', \\"). We only unescape if the code does not parse as valid Python,
    to avoid corrupting valid escape sequences inside strings, regexes, or raw strings.
    """
    import ast
    try:
        # If it parses as valid Python, don't touch it!
        ast.parse(code)
        return code
    except SyntaxError:
        pass

    # If it failed to parse, it likely contains literal escaped newlines/characters.
    # Try codecs.decode with unicode_escape first.
    try:
        import codecs
        decoded = codecs.decode(code, "unicode_escape")
        ast.parse(decoded)
        return decoded
    except Exception:
        pass

    # Fallback to targeted manual replacement
    fallback = (
        code.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\u0027", "'")
        .replace("\\u0022", '"')
        .replace('\\"', '"')
        .replace("\\'", "'")
    )
    return fallback


def _lever_from_statement(statement: str) -> str | None:
    text = statement.lower().replace("-", " ").replace("_", " ")
    matches = []
    for lever, pattern in (("batch_size", r"\bbatch(?:ing| size)?\b"),
                           ("threads", r"\bthreads?\b"),
                           ("precision", r"\b(?:precision|fp16|fp32|int8|quantization)\b")):
        if re.search(pattern, text):
            matches.append(lever)
    return matches[0] if len(matches) == 1 else None


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
        # Ensure the plan metrics include the objective metric, preserving the
        # semantic contract that hypothesis.expected_effect.metric ∈ experiment_plan.metrics.
        metrics = list(plan_output.metrics)
        if objective.metric not in metrics:
            metrics.append(objective.metric)

        plan = ExperimentPlan(
            hypothesis_id=hypothesis.id,
            baseline_id=baseline_id,
            variables=plan_output.variables,
            metrics=metrics,
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

        # Normalize code: some providers (e.g., Nebius) may escape characters
        # using JSON-style escape sequences (\\n, \\u0027, etc.) instead of
        # literal characters. Unescape them safely so the code is valid Python.
        raw_code = _normalize_code(code_output.code)

        # Preserve the generated intervention. Renaming a LEVER declaration
        # cannot make an unrelated implementation test the stated hypothesis.
        lever = _lever_from_statement(hypothesis.statement)
        code = raw_code

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
            workload_type="synthetic",
        )
        planned_levers = [_lever_from_statement(variable.name) for variable in plan.variables]
        declaration = EchoProviderCodePatcher._LEVER_ASSIGN.search(code)
        code_lever = declaration.group(1) if declaration else None
        if lever and (any(item and item != lever for item in planned_levers)
                      or (code_lever and code_lever != lever)):
            spec.intervention_status = "mismatch"
            spec.intervention_detail = "Hypothesis, planned variable, and generated lever disagree"
        elif (lever and planned_levers == [lever]
              and code == EchoReasoningProvider.synthetic_benchmark_code(objective.metric, lever)
              and plan.variables == EchoReasoningProvider()._plan(context).variables):
            spec.intervention_status = "verified_synthetic"
            spec.intervention_detail = (
                "Known synthetic implementation: candidate reduces arithmetic loop iterations; "
                "does not change actual model batch size, threads, or precision"
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
