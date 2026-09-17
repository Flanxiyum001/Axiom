from typing import List, Dict, Optional
from ..models.schemas import ExperimentResult, ResearchObjective, Metric, MetricDirection

class Evaluator:
    def evaluate(self, result: ExperimentResult, baseline: Dict[str, float], objective: ResearchObjective) -> Dict:
        """
        Compares experiment results against baseline and evaluates success criteria.
        """
        evaluation = {
            "experiment_id": result.experiment_id,
            "metrics_comparison": {},
            "success": False,
            "reasoning": []
        }

        # Simple logic: check if metrics improved or degraded within constraints
        # This is a placeholder for more complex logic
        is_success = True
        
        for metric in result.metrics:
            base_val = baseline.get(metric.name)
            if base_val is not None:
                delta = metric.value - base_val
                percent_change = (delta / base_val) * 100
                
                evaluation["metrics_comparison"][metric.name] = {
                    "baseline": base_val,
                    "experiment": metric.value,
                    "delta": delta,
                    "percent_change": percent_change
                }
                
                # Example constraint check: if metric is latency, check improvement
                if "latency" in metric.name and metric.direction == MetricDirection.MINIMIZE:
                    if percent_change > -20: # Needs at least 20% improvement
                        is_success = False
                        evaluation["reasoning"].append(f"Latency improvement {percent_change:.2f}% < 20%")
        
        evaluation["success"] = is_success
        return evaluation
