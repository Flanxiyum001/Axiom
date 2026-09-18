from __future__ import annotations

import json

from axiom.domain.interfaces import ProviderError, ReasoningProvider
from axiom.domain.models import Direction, ExpectedEffect, Hypothesis, ResearchObjective
from axiom.providers.schemas import AnalysisOutput, CodeOutput, PlanOutput
from axiom.domain.models import PlanVariable


_LEVERS = ("batch_size", "threads", "precision")


def _lever_for_iteration(iteration: int) -> str:
    return _LEVERS[iteration % len(_LEVERS)]


def _lever_from_text(text: str) -> str:
    lowered = text.lower()
    for lever in _LEVERS:
        if lever in lowered:
            return lever
    return "batch_size"


class EchoReasoningProvider(ReasoningProvider):
    name: str = "echo"

    def generate(self, *, system: str, prompt: str, context: dict[str, str], output_type: type) -> object:
        if output_type is Hypothesis:
            return self._hypothesis(context)
        if output_type is PlanOutput:
            return self._plan(context)
        if output_type is CodeOutput:
            return self._code(context)
        if output_type is AnalysisOutput:
            return self._analysis(context)
        raise ProviderError(f"Unsupported output type: {output_type}")

    def _hypothesis(self, context: dict[str, str]) -> Hypothesis:
        objective = ResearchObjective.model_validate_json(context["objective"])
        iteration = int(context.get("iteration", "0"))
        lever = _lever_for_iteration(iteration)
        return Hypothesis(
            objective_id=objective.id,
            statement=f"Optimizing {lever} will improve {objective.metric} beyond the current baseline",
            rationale=f"{lever} controls execution cost in the benchmark workload",
            expected_effect=ExpectedEffect(
                metric=objective.metric,
                direction=objective.direction,
                magnitude_percent=35.0,
                rationale=f"{lever} candidate path is expected to run faster",
            ),
            iteration=iteration,
        )

    def _plan(self, context: dict[str, str]) -> PlanOutput:
        objective = ResearchObjective.model_validate_json(context["objective"])
        lever = _lever_from_text(context.get("hypothesis", ""))
        return PlanOutput(
            variables=[PlanVariable(name=lever, baseline_value="default", candidate_value="optimized")],
            metrics=[objective.metric],
            repetitions=3,
            timeout_seconds=60.0,
        )

    def _code(self, context: dict[str, str]) -> CodeOutput:
        objective = ResearchObjective.model_validate_json(context["objective"])
        lever = _lever_from_text(context.get("hypothesis", ""))
        return CodeOutput(
            code=self.synthetic_benchmark_code(metric=objective.metric, lever=lever),
            environment={},
            description=f"A/B experiment measuring {objective.metric} via {lever}",
            parameters={},
        )

    def _analysis(self, context: dict[str, str]) -> AnalysisOutput:
        evaluation = json.loads(context["evaluation"])
        target_met = bool(evaluation.get("target_met", False))
        improvement = evaluation.get("improvement_percent")
        if target_met:
            return AnalysisOutput(
                hypothesis_supported=True,
                confidence=0.85,
                observations=[f"Measured improvement of {improvement:.2f}% met the target"],
                limitations=["Synthetic CPU benchmark"],
                conclusion="Hypothesis supported by measured improvement",
            )
        return AnalysisOutput(
            hypothesis_supported=False,
            confidence=0.6,
            observations=[f"Measured improvement of {improvement}% did not meet the target"],
            limitations=["Synthetic CPU benchmark"],
            conclusion="Hypothesis not supported by measured improvement",
        )

    @staticmethod
    def synthetic_benchmark_code(metric: str = "latency_ms", lever: str = "batch_size") -> str:
        return (
            "import json\n"
            "import os\n"
            "import time\n"
            "\n"
            f'LEVER = "{lever}"\n'
            f'METRIC = "{metric}"\n'
            'MODE = os.environ.get("__AXIOM_LEVER_MODE__", os.environ.get("AXIOM_LEVER_MODE", "baseline"))\n'
            "\n"
            "BASE_TICKS = 400000\n"
            "CANDIDATE_TICKS = 240000\n"
            'ticks = CANDIDATE_TICKS if MODE == "candidate" else BASE_TICKS\n'
            "\n"
            "samples = []\n"
            "for i in range(3):\n"
            "    start = time.perf_counter()\n"
            "    acc = 0\n"
            "    x = 1\n"
            "    for _ in range(ticks):\n"
            "        acc = (acc * 31 + x) % 1000003\n"
            "    elapsed_ms = (time.perf_counter() - start) * 1000.0\n"
            "    samples.append(elapsed_ms)\n"
            '    print(f"iter {i}: {elapsed_ms:.3f} ms", flush=True)\n'
            "\n"
            "print(json.dumps({\"metrics\": [{\"name\": METRIC, \"value\": v, \"unit\": \"ms\", \"iteration\": i} for i, v in enumerate(samples)]}))\n"
        )
