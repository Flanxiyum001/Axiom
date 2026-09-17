from typing import List, Dict
from .models.schemas import ResearchObjective, Hypothesis, ExperimentPlan, ExperimentStatus
from .experiments.runner import ExperimentRunner
from .experiments.evaluator import Evaluator
from .memory.store import ExperimentStore
import uuid

class Orchestrator:
    def __init__(self, objective: ResearchObjective, baseline: Dict[str, float]):
        self.objective = objective
        self.baseline = baseline
        self.runner = ExperimentRunner()
        self.evaluator = Evaluator()
        self.store = ExperimentStore()
        self.experiment_queue = ["fp16_optimization", "batch_size_optimization"]

    def run_loop(self):
        print(f"Starting research loop for objective: {self.objective.title}")
        
        for i in range(self.objective.max_experiments):
            if not self.experiment_queue:
                break
                
            exp_type = self.experiment_queue.pop(0)
            
            # 1. Create Hypothesis & Plan
            hypothesis = Hypothesis(
                objective_id=self.objective.id,
                title=f"Test {exp_type}",
                description="Deterministic test",
                rationale="Testing infrastructure",
                expected_outcome="Improvement"
            )
            
            plan = ExperimentPlan(
                hypothesis_id=hypothesis.id,
                title=exp_type,
                description="Deterministic test",
                parameters={},
                metrics=[],
                success_criteria="Improvement"
            )
            
            # 2. Run
            result = self.runner.run(plan, metric_definitions=self.objective.metrics)
            self.store.save_result(result)
            
            # 3. Evaluate
            evaluation = self.evaluator.evaluate(result, self.baseline, self.objective)
            print(f"Experiment {exp_type} finished. Success: {evaluation['success']}")
            
            if evaluation['success']:
                print("Objective achieved!")
                break
        
        print("Research loop finished.")
