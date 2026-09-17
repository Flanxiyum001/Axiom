from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from ..models.schemas import ExperimentResult, ResearchObjective, Metric, MetricDirection, MetricDefinition


@dataclass
class MetricComparison:
    name: str
    baseline: float
    experiment: float
    delta: float
    percent_change: float
    direction: MetricDirection
    constraint_satisfied: Optional[bool] = None
    constraint_details: Optional[str] = None


@dataclass
class EvaluationResult:
    experiment_id: str
    success: bool
    metrics_comparison: List[MetricComparison]
    overall_constraint_satisfied: bool
    reasoning: List[str]

    def to_dict(self) -> Dict:
        return {
            "experiment_id": self.experiment_id,
            "success": self.success,
            "metrics_comparison": {
                mc.name: {
                    "baseline": mc.baseline,
                    "experiment": mc.experiment,
                    "delta": mc.delta,
                    "percent_change": mc.percent_change,
                    "direction": mc.direction.value,
                    "constraint_satisfied": mc.constraint_satisfied,
                    "constraint_details": mc.constraint_details,
                }
                for mc in self.metrics_comparison
            },
            "overall_constraint_satisfied": self.overall_constraint_satisfied,
            "reasoning": self.reasoning,
        }
class Evaluator:
    def evaluate(self, result: ExperimentResult, baseline: Dict[str, float], objective: ResearchObjective) -> Dict:
        metric_defs = {md.name: md for md in objective.metrics}
        metrics_comparison = []
        reasoning = []
        all_constraints_satisfied = True

        for metric in result.metrics:
            base_val = baseline.get(metric.name)
            if base_val is None:
                reasoning.append(f"Metric '{metric.name}' not found in baseline, skipping")
                continue

            metric_def = metric_defs.get(metric.name)
            direction = metric_def.direction if metric_def else metric.direction

            delta = metric.value - base_val
            percent_change = (delta / base_val) * 100 if base_val != 0 else 0.0

            constraint_satisfied = None
            constraint_details = None

            if objective.constraints:
                constraint_satisfied, constraint_details = self._check_constraints(
                    metric.name, base_val, metric.value, delta, percent_change,
                    direction, objective.constraints
                )
                if constraint_satisfied is not None and not constraint_satisfied:
                    all_constraints_satisfied = False

            if objective.target:
                target_satisfied, target_details = self._check_targets(
                    metric.name, base_val, metric.value, delta, percent_change,
                    direction, objective.target
                )
                if target_satisfied is not None and not target_satisfied:
                    all_constraints_satisfied = False
                if constraint_satisfied is None:
                    constraint_satisfied = target_satisfied
                    constraint_details = target_details

            mc = MetricComparison(
                name=metric.name,
                baseline=base_val,
                experiment=metric.value,
                delta=delta,
                percent_change=percent_change,
                direction=direction,
                constraint_satisfied=constraint_satisfied,
                constraint_details=constraint_details,
            )
            metrics_comparison.append(mc)

            if constraint_details:
                reasoning.append(f"{metric.name}: {constraint_details}")

        success = all_constraints_satisfied

        evaluation = EvaluationResult(
            experiment_id=str(result.experiment_id),
            success=success,
            metrics_comparison=metrics_comparison,
            overall_constraint_satisfied=all_constraints_satisfied,
            reasoning=reasoning,
        )

        return evaluation.to_dict()

    def _check_constraints(
        self,
        metric_name: str,
        baseline_val: float,
        experiment_val: float,
        delta: float,
        percent_change: float,
        direction: MetricDirection,
        constraints: Dict[str, Any]
    ) -> tuple[Optional[bool], Optional[str]]:
        if metric_name == "accuracy" and "max_accuracy_degradation" in constraints:
            max_degradation = constraints["max_accuracy_degradation"]
            degradation = baseline_val - experiment_val
            satisfied = degradation <= max_degradation
            details = (
                f"Accuracy degradation {degradation:.4f} "
                f"{'<=' if satisfied else '>'} {max_degradation} "
                f"{'(PASS)' if satisfied else '(FAIL)'}"
            )
            return satisfied, details

        if direction == MetricDirection.MINIMIZE and "max_increase" in constraints:
            max_increase = constraints["max_increase"]
            increase = experiment_val - baseline_val
            satisfied = increase <= max_increase
            details = (
                f"{metric_name} increase {increase:.2f} "
                f"{'<=' if satisfied else '>'} {max_increase} "
                f"{'(PASS)' if satisfied else '(FAIL)'}"
            )
            return satisfied, details

        return None, None

    def _check_targets(
        self,
        metric_name: str,
        baseline_val: float,
        experiment_val: float,
        delta: float,
        percent_change: float,
        direction: MetricDirection,
        targets: Dict[str, Any]
    ) -> tuple[Optional[bool], Optional[str]]:
        if metric_name == "latency_ms" and "latency_reduction" in targets:
            target_reduction = targets["latency_reduction"]
            actual_reduction = -percent_change / 100.0
            satisfied = actual_reduction >= target_reduction
            details = (
                f"Latency reduction {actual_reduction:.2%} "
                f"{'>=' if satisfied else '<'} {target_reduction:.0%} "
                f"{'(PASS)' if satisfied else '(FAIL)'}"
            )
            return satisfied, details

        if metric_name == "throughput" and "throughput_increase" in targets:
            target_increase = targets["throughput_increase"]
            actual_increase = percent_change / 100.0
            satisfied = actual_increase >= target_increase
            details = (
                f"Throughput increase {actual_increase:.2%} "
                f"{'>=' if satisfied else '<'} {target_increase:.0%} "
                f"{'(PASS)' if satisfied else '(FAIL)'}"
            )
            return satisfied, details

        if metric_name == "accuracy" and "min_accuracy" in targets:
            min_accuracy = targets["min_accuracy"]
            satisfied = experiment_val >= min_accuracy
            details = (
                f"Accuracy {experiment_val:.4f} "
                f"{'>=' if satisfied else '<'} {min_accuracy:.4f} "
                f"{'(PASS)' if satisfied else '(FAIL)'}"
            )
            return satisfied, details

        return None, None