"""Deterministic Mock LLM Provider for AXIOM.

This provider returns predictable, valid responses for testing and development.
It inspects the requested output_type and context to generate appropriate
domain objects without any external API calls.
"""

import json
from typing import TypeVar

from pydantic import BaseModel

from .base import LLMProvider, ProviderError
from ..models.schemas import (
    ResearchObjective,
    Hypothesis,
    ExperimentPlan,
    MetricDefinition,
    MetricDirection,
    ExperimentStatus,
    ExperimentResult,
    Analysis,
)
from uuid import UUID

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(LLMProvider):
    """Deterministic mock provider for testing.

    Returns pre-defined valid responses based on the output_type.
    The responses are designed to be valid for the current optimization objective.
    """

    name = "mock"

    def __init__(self, *, seed: int = 42):
        self._seed = seed
        self._call_count = 0

    def generate(
        self,
        *,
        system: str,
        prompt: str,
        context: dict[str, str],
        output_type: type[T],
    ) -> T:
        """Generate a deterministic mock response for the given output type."""
        self._call_count += 1

        if output_type is Hypothesis:
            return self._generate_hypothesis(context)  # type: ignore[return-value]
        elif output_type is ExperimentPlan:
            return self._generate_experiment_plan(context)  # type: ignore[return-value]
        elif output_type is Analysis:
            return self._generate_analysis(context)  # type: ignore[return-value]
        else:
            raise ProviderError(f"Mock provider does not support output type: {output_type}")

    def _generate_hypothesis(self, context: dict[str, str]) -> Hypothesis:
        """Generate a deterministic hypothesis based on context."""
        objective_json = context.get("objective", "{}")
        iteration_str = context.get("iteration", "0")
        prior_evidence = context.get("prior_evidence", "")

        try:
            objective = ResearchObjective.model_validate_json(objective_json)
        except Exception:
            objective = ResearchObjective(
                title="Default Objective",
                description="Reduce inference latency",
                metrics=[MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE)],
                constraints={},
                target={},
            )

        iteration = int(iteration_str)

        # Create deterministic sequence for genuine iteration:
        # Iteration 0: Batch Size Tuning (should fail)
        # Iteration 1: FP16 Precision Optimization (should succeed)
        # Iteration 2+: Repeat FP16 (but orchestrator will prevent duplicates)
        
        if iteration == 0:
            # First hypothesis: Batch Size Tuning
            return Hypothesis(
                objective_id=objective.id,
                title="Batch Size Tuning",
                description="Increase batch size to improve throughput and amortize overhead",
                rationale="Larger batch sizes improve hardware utilization and throughput, though latency per sample may increase",
                expected_outcome="Throughput increase of 2-4x with moderate latency increase",
                status=ExperimentStatus.PENDING,
            )
        else:
            # Second hypothesis: FP16 Precision Optimization
            return Hypothesis(
                objective_id=objective.id,
                title="FP16 Precision Optimization",
                description="Apply FP16 quantization to reduce inference latency while maintaining acceptable accuracy",
                rationale="FP16 reduces memory bandwidth and compute requirements, typically yielding 30-50% latency reduction with <1% accuracy degradation",
                expected_outcome="Latency reduction of ~40% with accuracy degradation <1%",
                status=ExperimentStatus.PENDING,
            )

    def _generate_experiment_plan(self, context: dict[str, str]) -> ExperimentPlan:
        """Generate a deterministic experiment plan based on context."""
        hypothesis_json = context.get("hypothesis", "{}")

        try:
            hypothesis = Hypothesis.model_validate_json(hypothesis_json)
        except Exception:
            hypothesis = Hypothesis(
                objective_id="unknown",
                title="Unknown Hypothesis",
                description="",
                rationale="",
                expected_outcome="",
            )

        title_lower = hypothesis.title.lower()

        if "batch" in title_lower:
            exp_type = "batch_size_optimization"
            params = {"batch_size": 4}
            metrics = ["latency_ms", "accuracy", "throughput", "gpu_memory_mb"]
            success_criteria = "Throughput increase >= 50% with accuracy maintained"
        elif "fp16" in title_lower or "precision" in title_lower:
            exp_type = "fp16_optimization"
            params = {}
            metrics = ["latency_ms", "accuracy", "throughput", "gpu_memory_mb"]
            success_criteria = "Latency reduction >= 20% AND accuracy degradation <= 1%"
        elif "int8" in title_lower or "quantization" in title_lower:
            exp_type = "fp16_optimization"
            params = {"precision": "int8"}
            metrics = ["latency_ms", "accuracy", "throughput", "gpu_memory_mb"]
            success_criteria = "Latency reduction >= 30% AND accuracy degradation <= 2%"
        else:
            exp_type = "baseline_benchmark"
            params = {}
            metrics = ["latency_ms", "accuracy", "throughput", "gpu_memory_mb"]
            success_criteria = "Establish baseline metrics"

        return ExperimentPlan(
            hypothesis_id=hypothesis.id,
            title=exp_type,
            description=f"Experiment to test: {hypothesis.title}",
            parameters=params,
            metrics=metrics,
            success_criteria=success_criteria,
        )

    def _generate_analysis(self, context: dict[str, str]) -> Analysis:
        """Generate a deterministic Analysis based on context."""
        experiment_id_str = context.get("experiment_result", "{}")
        try:
            result = ExperimentResult.model_validate_json(experiment_id_str)
            experiment_id = result.experiment_id
        except Exception:
            experiment_id = UUID("00000000-0000-0000-0000-000000000000")

        objective_id_str = context.get("objective", "{}")
        try:
            objective = ResearchObjective.model_validate_json(objective_id_str)
            objective_id = objective.id
        except Exception:
            objective_id = UUID("00000000-0000-0000-0000-000000000000")

        hypothesis_title = context.get("hypothesis", "Unknown")
        success = result.status == ExperimentStatus.COMPLETED

        # Build observations from metrics
        observations = [
            f"Experiment status: {result.status.value}"
        ]
        for m in result.metrics:
            observations.append(
                f"Metric '{m.name}': {m.value} {m.unit}"
            )

        # Determine if the hypothesis is supported based on evaluation, not just experiment completion
        # Parse evaluation from context if available
        evaluation_success = False
        try:
            evaluation_data = context.get("evaluation", {})
            # Handle both dict and JSON string formats
            if isinstance(evaluation_data, str):
                evaluation_dict = json.loads(evaluation_data)
            else:
                evaluation_dict = evaluation_data
            evaluation_success = evaluation_dict.get("success", False)
        except (json.JSONDecodeError, AttributeError, TypeError):
            # Fallback to experiment completion if evaluation parsing fails
            evaluation_success = success
        
        if evaluation_success:
            summary = (
                f"The experiment '{hypothesis_title}' completed successfully. "
                f"The deterministic evaluation confirmed the experiment met its criteria."
            )
            interpretation = (
                "The hypothesis was supported by the evidence. "
                "The measured metrics show the expected improvement."
            )
            limitations = [
                "Results are based on simulated metrics; real-world performance may vary.",
                "Only a single experiment was run; statistical significance was not verified.",
            ]
            next_direction = (
                "Proceed to validate these results with additional repetitions "
                "and consider edge cases before finalizing."
            )
        else:
            summary = (
                f"The experiment '{hypothesis_title}' completed successfully. "
                f"The deterministic evaluation indicates the experiment did not meet its objective."
            )
            interpretation = (
                "The hypothesis was not supported by the evidence. "
                "While some metrics may show improvement, the defined objective was not achieved."
            )
            limitations = [
                "Results are based on simulated metrics; real-world performance may vary.",
                "Only a single experiment was run; statistical significance was not verified.",
            ]
            next_direction = (
                "Investigate alternative approaches or adjust parameters "
                "to better address the research objective."
            )

        return Analysis(
            experiment_id=experiment_id,
            objective_id=objective_id,
            hypothesis_title=hypothesis_title,
            summary=summary,
            observations=observations,
            interpretation=interpretation,
            limitations=limitations,
            recommended_next_direction=next_direction,
        )