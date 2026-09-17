import sys
import os
import uuid

# Add the root directory to sys.path to allow importing backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from backend.models.schemas import ResearchObjective, MetricDefinition, MetricDirection
from backend.orchestrator import Orchestrator

def run_demo():
    print("AXIOM AUTONOMOUS RESEARCH")
    print("==========================")
    print("\nNOTE: This is a LOCAL SIMULATION using deterministic mock experiments.")
    print("No real GPU benchmarking is being performed.\n")

    # 1. Define Objective
    objective = ResearchObjective(
        title="Reduce Inference Latency",
        description="Reduce inference latency by at least 20% while keeping accuracy degradation below 1%.",
        metrics=[
            MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE),
            MetricDefinition(name="accuracy", unit="ratio", direction=MetricDirection.MAXIMIZE)
        ],
        constraints={"max_accuracy_degradation": 0.01},
        target={"latency_reduction": 0.20},
        max_experiments=5
    )

    # 2. Define Baseline
    baseline = {
        "accuracy": 0.914,
        "latency_ms": 142.0,
        "throughput": 70.0,
        "gpu_memory_mb": 5200.0
    }

    print(f"Objective: {objective.title}")
    print(f"Description: {objective.description}")
    print(f"\nBaseline Metrics:")
    for k, v in baseline.items():
        print(f"  - {k}: {v}")
    print("-" * 30)

    # 3. Initialize and Run Orchestrator
    # We'll wrap the orchestrator to print progress
    class DemoOrchestrator(Orchestrator):
        def run_loop(self):
            print(f"\nStarting research loop...")
            
            for i in range(self.objective.max_experiments):
                if not self.experiment_queue:
                    print("\nNo more hypotheses to test.")
                    break
                    
                exp_type = self.experiment_queue.pop(0)
                print(f"\nExperiment {i+1}: {exp_type}")
                
                # Create Hypothesis & Plan
                hypothesis = Hypothesis(
                    objective_id=self.objective.id,
                    title=f"Test {exp_type}",
                    description=f"Evaluating {exp_type} for latency optimization.",
                    rationale="Simulated optimization step.",
                    expected_outcome="Improved performance."
                )
                
                plan = ExperimentPlan(
                    hypothesis_id=hypothesis.id,
                    title=exp_type,
                    description=f"Execution of {exp_type}",
                    parameters={},
                    metrics=["latency_ms", "accuracy"],
                    success_criteria="Latency reduction >= 20%"
                )
                
                # Run
                result = self.runner.run(plan)
                self.store.save_result(result)
                
                # Print Results
                for m in result.metrics:
                    print(f"  {m.name}: {m.value} {m.unit}")
                
                # Evaluate
                evaluation = self.evaluator.evaluate(result, self.baseline, self.objective)
                
                if evaluation['success']:
                    print("\n[!] SUCCESS: Objective achieved.")
                    
                    # Calculate final stats
                    comp = evaluation["metrics_comparison"].get("latency_ms", {})
                    print(f"\nFinal Result:")
                    print(f"  Latency improvement: {abs(comp.get('percent_change', 0)):.2f}%")
                    
                    acc_comp = evaluation["metrics_comparison"].get("accuracy", {})
                    acc_deg = (acc_comp.get('baseline', 0) - acc_comp.get('experiment', 0))
                    print(f"  Accuracy degradation: {acc_deg:.3f} points")
                    print(f"  Experiments executed: {i+1}")
                    return
                else:
                    print("  Status: Objective not yet met.")
            
            print("\n[!] Research loop finished without achieving objective.")

    from backend.models.schemas import Hypothesis, ExperimentPlan
    
    orch = DemoOrchestrator(objective, baseline)
    orch.run_loop()

if __name__ == "__main__":
    run_demo()
