import time
import uuid
from typing import Dict, Callable, List, Optional
from ..models.schemas import ExperimentPlan, ExperimentResult, ExperimentStatus, Metric, MetricDirection

# --- Metric Direction Registry ---
# Centralized mapping of metric names to their optimization directions.
# This ensures consistency across runner, evaluator, and objective definitions.
METRIC_DIRECTIONS: Dict[str, MetricDirection] = {
    "accuracy": MetricDirection.MAXIMIZE,
    "throughput": MetricDirection.MAXIMIZE,
    "latency_ms": MetricDirection.MINIMIZE,
    "gpu_memory_mb": MetricDirection.MINIMIZE,
}

def get_metric_direction(name: str) -> MetricDirection:
    """Get the optimization direction for a metric name. Defaults to MAXIMIZE for unknown metrics."""
    return METRIC_DIRECTIONS.get(name, MetricDirection.MAXIMIZE)

# --- Mock Experiment Implementations ---

def baseline_benchmark(params: Dict) -> Dict[str, float]:
    """Simulates a baseline inference benchmark."""
    return {
        "accuracy": 0.914,
        "latency_ms": 142.0,
        "throughput": 70.0,
        "gpu_memory_mb": 5200.0
    }

def fp16_optimization(params: Dict) -> Dict[str, float]:
    """Simulates FP16 optimization: slightly lower accuracy, much lower latency."""
    return {
        "accuracy": 0.910,
        "latency_ms": 85.0,
        "throughput": 110.0,
        "gpu_memory_mb": 3100.0
    }

def batch_size_optimization(params: Dict) -> Dict[str, float]:
    """Simulates batch size tuning."""
    batch_size = params.get("batch_size", 1)
    # Simple linear scaling simulation
    return {
        "accuracy": 0.914,
        "latency_ms": 142.0 + (batch_size * 10),
        "throughput": 70.0 * batch_size,
        "gpu_memory_mb": 5200.0 + (batch_size * 500)
    }

# Registry of allowed experiments
EXPERIMENT_REGISTRY: Dict[str, Callable[[Dict], Dict[str, float]]] = {
    "baseline_benchmark": baseline_benchmark,
    "fp16_optimization": fp16_optimization,
    "batch_size_optimization": batch_size_optimization,
}

# --- Runner ---

class ExperimentRunner:
    def run(self, plan: ExperimentPlan, metric_definitions: Optional[List] = None) -> ExperimentResult:
        """
        Run an experiment plan.
        
        Args:
            plan: The experiment plan to execute.
            metric_definitions: Optional list of MetricDefinition from the ResearchObjective
                to use for correct metric directions. If not provided, uses the global registry.
        """
        start_time = time.time()
        
        # Check if experiment is registered
        if plan.title not in EXPERIMENT_REGISTRY:
            return ExperimentResult(
                experiment_id=plan.id,
                status=ExperimentStatus.FAILED,
                metrics=[],
                duration=0.0,
                logs=f"Error: Experiment '{plan.title}' not found in registry.",
                error="ExperimentNotFound"
            )
        
        try:
            # Execute the registered function
            experiment_func = EXPERIMENT_REGISTRY[plan.title]
            raw_metrics = experiment_func(plan.parameters)
            
            # Build direction lookup from metric_definitions if provided, else use global registry
            direction_map = {}
            if metric_definitions:
                for md in metric_definitions:
                    direction_map[md.name] = md.direction
            
            # Convert to Metric objects with correct directions
            metrics = [
                Metric(
                    name=k, 
                    value=v, 
                    unit="unit", 
                    direction=direction_map.get(k, get_metric_direction(k))
                ) 
                for k, v in raw_metrics.items()
            ]
            
            duration = time.time() - start_time
            
            return ExperimentResult(
                experiment_id=plan.id,
                status=ExperimentStatus.COMPLETED,
                metrics=metrics,
                duration=duration,
                logs=f"Successfully executed {plan.title} with params {plan.parameters}",
                conclusion="Experiment completed successfully."
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return ExperimentResult(
                experiment_id=plan.id,
                status=ExperimentStatus.FAILED,
                metrics=[],
                duration=duration,
                logs=str(e),
                error=type(e).__name__
            )
