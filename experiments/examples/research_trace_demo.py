#!/usr/bin/env python
"""
AXIOM Research Trace Demo

This demo runs the autonomous research loop and prints a beautifully formatted
research trace showing the interaction between LLM agents (Researcher, Planner, Analyst)
and deterministic infrastructure (Runner, Evaluator).
"""

import sys
import os

# Add the root directory to sys.path to allow importing backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from backend.models.schemas import ResearchObjective, MetricDefinition, MetricDirection
from backend.orchestrator import Orchestrator
from backend.llm.mock import MockLLMProvider
from backend.agents.researcher import ResearcherAgent
from backend.agents.planner import PlannerAgent
from backend.agents.analyst import AnalystAgent
from backend.experiments.runner import ExperimentRunner
from backend.experiments.evaluator import Evaluator
from backend.memory.store import ResearchMemoryStore
from backend.models.schemas import Hypothesis, ExperimentPlan, ExperimentResult, ExperimentStatus, Analysis
from uuid import UUID


def print_header(title: str, char: str = "="):
    """Print a formatted header."""
    width = 50
    print(char * width)
    print(title.center(width))
    print(char * width)


def print_section(title: str, char: str = "-"):
    """Print a section header."""
    width = 50
    print(char * width)
    print(title)
    print(char * width)


def format_metrics(metrics, prefix="  "):
    """Format metrics for display."""
    lines = []
    for m in metrics:
        lines.append(f"{prefix}{m.name}: {m.value} {m.unit}")
    return "\n".join(lines)
def run_research_trace_demo():
    """Run the demo and print a formatted research trace."""
    
    print_header("AXIOM AUTONOMOUS RESEARCH LAB")
    print()
    
    # 1. Define Objective
    objective = ResearchObjective(
        title="Reduce Inference Latency",
        description="Reduce inference latency by \u003e=20% while keeping accuracy degradation \u003c=1%",
        metrics=[
            MetricDefinition(name="latency_ms", unit="ms", direction=MetricDirection.MINIMIZE),
            MetricDefinition(name="accuracy", unit="ratio", direction=MetricDirection.MAXIMIZE),
            MetricDefinition(name="throughput", unit="samples/s", direction=MetricDirection.MAXIMIZE),
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
    
    # Print Objective
    print("OBJECTIVE")
    print(f"  {objective.description}")
    print()
    
    print("BASELINE METRICS")
    for k, v in baseline.items():
        print(f"  {k}: {v}")
    print()
    
    # Initialize components
    runner = ExperimentRunner()
    evaluator = Evaluator()
    store = ResearchMemoryStore()
    provider = MockLLMProvider()
    researcher = ResearcherAgent(provider)
    planner = PlannerAgent(provider)
    analyst = AnalystAgent(provider)
    
    # Track history
    prior_hypotheses = []
    prior_results = []
    prior_evidence = []
    analyses = []
    tried_experiment_types = set()
    tried_hypothesis_titles = set()
    
    iteration = 0
    objective_achieved = False
    
    while iteration < objective.max_experiments and not objective_achieved:
        # TODO: rest of loop implementation
        iteration += 1
        
        print_section(f"RESEARCH ITERATION {iteration:02d}")
        print()
        
        # Step 1: Researcher proposes hypothesis
        hypothesis = researcher.propose(
            objective=objective,
            iteration=iteration - 1,
            prior_hypotheses=prior_hypotheses,
            prior_results=prior_results,
            prior_evidence=prior_evidence,
        )
        
        # Check for duplicate hypothesis title
        if hypothesis.title in tried_hypothesis_titles:
            print("RESEARCHER")
            print(f"  Hypothesis: {hypothesis.title} (DUPLICATE - skipping)")
            print()
            continue
        
        tried_hypothesis_titles.add(hypothesis.title)
        
        print("RESEARCHER")
        print(f"  Hypothesis: {hypothesis.title}")
        print(f"  Rationale: {hypothesis.rationale}")
        print()
        
        # Step 2: Planner designs experiment
        available_experiments = ["baseline_benchmark", "fp16_optimization", "batch_size_optimization"]
        plan = planner.design(
            hypothesis=hypothesis,
            objective=objective,
            available_experiments=available_experiments,
        )
        
        # Check for duplicate experiment type
        if plan.title in tried_experiment_types:
            print("PLANNER")
            print(f"  Experiment: {plan.title} (DUPLICATE - skipping)")
            print()
            continue
        
        tried_experiment_types.add(plan.title)
        
        print("PLANNER")
        print(f"  Experiment: {plan.title}")
        if plan.parameters:
            print(f"  Parameters: {plan.parameters}")
        print()
        
        # Step 3: Execute experiment
        result = runner.run(plan, metric_definitions=objective.metrics)
        
        print("EXECUTION")
        for m in result.metrics:
            print(f"  {m.name}: {m.value} {m.unit}")
        print()
        
        # Step 4: Evaluate result
        evaluation = evaluator.evaluate(result, baseline, objective)
        
        print("EVALUATOR")
        # Latency target
        latency_comp = evaluation["metrics_comparison"].get("latency_ms", {})
        latency_satisfied = latency_comp.get("constraint_satisfied", False)
        latency_details = latency_comp.get("constraint_details", "")
        print(f"  Latency target: {'SATISFIED' if latency_satisfied else 'NOT SATISFIED'}")
        if latency_details:
            print(f"    {latency_details}")
        
        # Accuracy constraint
        acc_comp = evaluation["metrics_comparison"].get("accuracy", {})
        acc_satisfied = acc_comp.get("constraint_satisfied", False)
        acc_details = acc_comp.get("constraint_details", "")
        print(f"  Accuracy constraint: {'SATISFIED' if acc_satisfied else 'NOT SATISFIED'}")
        if acc_details:
            print(f"    {acc_details}")
        
        # Overall objective
        print(f"  OBJECTIVE: {'ACHIEVED' if evaluation['success'] else 'NOT ACHIEVED'}")
        print()
        
        # Step 5: Analyst interprets evidence
        analysis = analyst.analyze(
            result=result,
            evaluation=evaluation,
            objective=objective,
            hypothesis=hypothesis,
            prior_context=analyses,
        )
        analyses.append(analysis)
        
        print("ANALYST")
        interpretation_lines = analysis.interpretation.split(". ")
        for line in interpretation_lines:
            if line.strip():
                print(f"  {line.strip()}.")
        print()
        
        # Track history
        prior_hypotheses.append(hypothesis)
        prior_results.append(result)
        prior_evidence.append(evaluation)
        
        if evaluation["success"]:
            objective_achieved = True
            print_section("RESEARCH COMPLETE")
            print()
            print("OBJECTIVE ACHIEVED")
            print(f"  Latency improvement: {abs(latency_comp.get('percent_change', 0)):.1f}%")
            acc_deg = acc_comp.get('baseline', 0) - acc_comp.get('experiment', 0)
            print(f"  Accuracy degradation: {acc_deg:.3f} points")
            print(f"  Experiments executed: {iteration}")
            break

