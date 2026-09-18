from typing import List, Dict, Any, Optional, Set
from .models.schemas import (
    ResearchObjective,
    Hypothesis,
    ExperimentPlan,
    ExperimentStatus,
    Analysis,
    ExperimentResult,
)
from .experiments.runner import ExperimentRunner, EXPERIMENT_REGISTRY
from .experiments.evaluator import Evaluator
from .memory.store import ResearchMemoryStore
from .llm.mock import MockLLMProvider
from .llm.base import LLMProvider
from .agents.researcher import ResearcherAgent
from .agents.planner import PlannerAgent
from .agents.analyst import AnalystAgent
from .llm.base import ProviderError
from .config import settings

# Conditionally import Nebius provider to avoid hard dependency
try:
    from .llm.nebius import NebiusLLMProvider
    NEBIUS_AVAILABLE = True
except ImportError:
    NEBIUS_AVAILABLE = False
    NebiusLLMProvider = None  # type: ignore


class Orchestrator:
    """Orchestrates the full autonomous research loop:

    1. Receive objective
    2. Ask Researcher for hypothesis
    3. Validate hypothesis
    4. Ask Planner for experiment plan
    5. Validate experiment type against registry
    6. Execute experiment
    7. Evaluate result deterministically
    8. Store all evidence in memory
    9. Ask Analyst to interpret evidence
    10. If objective is satisfied, stop
    11. Otherwise ask Researcher for another hypothesis
    12. Continue until max_experiments is reached

    The Orchestrator wires the deterministic infrastructure (runner, evaluator)
    with the LLM-driven agents (researcher, planner, analyst) and maintains
    a structured in-memory store of all research artifacts so the next
    Researcher call can see what has already been tried.

    Prevents duplicate experiments by tracking tried hypotheses and experiment types.
    """

    def __init__(self, objective: ResearchObjective, baseline: Dict[str, float]):
        self.objective = objective
        self.baseline = baseline
        self.runner = ExperimentRunner()
        self.evaluator = Evaluator()
        self.store = ResearchMemoryStore()

        # Initialize LLM provider based on configuration
        provider_name = settings.axiom_llm_provider.lower()
        if provider_name == "nebius":
            if not NEBIUS_AVAILABLE:
                raise RuntimeError(
                    "Nebius provider requested but openai package is not installed. "
                    "Install with: pip install openai"
                )
            self.provider = NebiusLLMProvider(
                api_key=settings.nebius_api_key,
                base_url=settings.nebius_base_url,
                model=settings.nebius_model,
                request_timeout=settings.nebius_request_timeout,
                max_retries=settings.nebius_max_retries,
            )
            print(f"[Orchestrator] Using Nebius LLM provider (model={settings.nebius_model})")
        else:
            # Default to mock provider (deterministic, no API key needed)
            self.provider = MockLLMProvider()
            print("[Orchestrator] Using Mock LLM provider")

        self.researcher = ResearcherAgent(self.provider)
        self.planner = PlannerAgent(self.provider)
        self.analyst = AnalystAgent(self.provider)

        self.iteration = 0
        self.prior_hypotheses: list[Hypothesis] = []
        self.prior_results: list[ExperimentResult] = []
        self.prior_evidence: list[Dict[str, Any]] = []
        self.analyses: list[Analysis] = []

        # Track tried experiment types to prevent duplicates
        self._tried_experiment_types: Set[str] = set()
        # Track tried hypothesis titles to prevent duplicates
        self._tried_hypothesis_titles: Set[str] = set()

        # Store the objective in memory
        self.store.save_objective(objective)

    def _validate_hypothesis(self, hypothesis: Hypothesis) -> bool:
        """Validate that the hypothesis is well-formed and not a duplicate."""
        if not hypothesis.title or not hypothesis.title.strip():
            print("[Orchestrator] Hypothesis validation failed: empty title")
            return False
        if not hypothesis.description or not hypothesis.description.strip():
            print("[Orchestrator] Hypothesis validation failed: empty description")
            return False
        if not hypothesis.rationale or not hypothesis.rationale.strip():
            print("[Orchestrator] Hypothesis validation failed: empty rationale")
            return False
        if not hypothesis.expected_outcome or not hypothesis.expected_outcome.strip():
            print("[Orchestrator] Hypothesis validation failed: empty expected_outcome")
            return False
        if hypothesis.title in self._tried_hypothesis_titles:
            print(f"[Orchestrator] Duplicate hypothesis: '{hypothesis.title}'")
            return False
        return True

    def _validate_experiment_type(self, plan: ExperimentPlan) -> bool:
        """Validate that the experiment type exists in the registry."""
        if plan.title not in EXPERIMENT_REGISTRY:
            print(f"[Orchestrator] Experiment validation failed: '{plan.title}' not in registry")
            return False
        return True

    def _is_duplicate_experiment(self, plan: ExperimentPlan) -> bool:
        """Check if this experiment type has already been tried."""
    def run_loop(self) -> Dict[str, Any]:
        """Execute the autonomous research loop.

        Returns:
            Dictionary with loop results including success status, iterations run,
            and final analysis.
        """
        print(f"Starting research loop for objective: {self.objective.title}")
        print(f"Max experiments: {self.objective.max_experiments}")

        objective_achieved = False
        final_analysis = None

        for i in range(self.objective.max_experiments):
            self.iteration = i
            print(f"\n{'='*60}")
            print(f"ITERATION {i + 1}/{self.objective.max_experiments}")
            print(f"{'='*60}")

            # Step 2: Ask Researcher for hypothesis
            memory_context = self.store.get_research_context(self.objective.id)
            hypothesis = self.researcher.propose(
                self.objective,
                iteration=self.iteration,
                prior_hypotheses=self.prior_hypotheses,
                prior_results=self.prior_results,
                prior_evidence=self.prior_evidence,
                memory_context=memory_context,
            )
            print(f"[Researcher] Proposed hypothesis: {hypothesis.title}")

            # Step 3: Validate hypothesis
            if not self._validate_hypothesis(hypothesis):
                print("[Orchestrator] Invalid or duplicate hypothesis, requesting another...")
                # Try to get another hypothesis (max 3 retries)
                retry_count = 0
                while retry_count < 3:
                    retry_count += 1
                    hypothesis = self.researcher.propose(
                        self.objective,
                        iteration=self.iteration,
                        prior_hypotheses=self.prior_hypotheses,
                        prior_results=self.prior_results,
                        prior_evidence=self.prior_evidence,
                        memory_context=memory_context,
                    )
                    print(f"[Researcher] Retry {retry_count}: Proposed hypothesis: {hypothesis.title}")
                    if self._validate_hypothesis(hypothesis):
                        break
                else:
                    print("[Orchestrator] Failed to get valid hypothesis after retries, stopping loop")
                    break

            # Track this hypothesis
            self._tried_hypothesis_titles.add(hypothesis.title)

            # Store hypothesis in memory
            self.store.save_hypothesis(hypothesis)

            # Step 4: Ask Planner for experiment plan
            plan = self.planner.design(hypothesis, self.objective)
            print(f"[Planner] Designed plan: {plan.title}")

            # Step 5: Validate experiment type against registry
            if not self._validate_experiment_type(plan):
                print("[Orchestrator] Invalid experiment type, skipping to next iteration")
                continue

            # Prevent duplicate experiments
            if self._is_duplicate_experiment(plan):
                print(f"[Orchestrator] Experiment type '{plan.title}' already tried, skipping")
                continue

            # Track this experiment type
            self._tried_experiment_types.add(plan.title)

            # Store plan in memory
            self.store.save_plan(plan)

            # Step 6: Execute experiment
            result = self.runner.run(
                plan, metric_definitions=self.objective.metrics
            )
            self.store.save_result(result)
            print(f"[Runner] Experiment completed: {result.status}")

            # Step 7: Evaluate result deterministically
            evaluation = self.evaluator.evaluate(
                result, self.baseline, self.objective
            )
            success = evaluation.get('success', False)
            print(f"[Evaluator] Success: {success}")

            # Store evaluation in memory
            self.store.save_evaluation(result.experiment_id, evaluation)

            # Step 8: Store all evidence in memory (already done above)

            # Step 9: Ask Analyst to interpret evidence
            analysis = self.analyst.analyze(
                result=result,
                evaluation=evaluation,
                objective=self.objective,
                hypothesis=hypothesis,
                prior_context=self.analyses,
            )
            self.analyses.append(analysis)
            self.store.save_analysis(analysis)
            print(f"[Analyst] Analysis: {analysis.summary}")

            # Track history for next iteration
            self.prior_hypotheses.append(hypothesis)
            self.prior_results.append(result)
            self.prior_evidence.append(evaluation)

            # Step 10: If objective is satisfied, stop
            if success:
                print("\n[Orchestrator] OBJECTIVE ACHIEVED!")
                objective_achieved = True
                final_analysis = analysis
                break

            # Step 11: Otherwise continue to next iteration (loop continues)

        # Step 12: Loop ends when max_experiments reached or objective achieved
        print(f"\n{'='*60}")
        print("Research loop finished.")
        print(f"Total iterations: {self.iteration + 1}")
        print(f"Objective achieved: {objective_achieved}")
        print(f"Experiments tried: {list(self._tried_experiment_types)}")
        print(f"{'='*60}")

        return {
            "objective_achieved": objective_achieved,
            "iterations": self.iteration + 1,
            "tried_experiment_types": list(self._tried_experiment_types),
            "tried_hypotheses": list(self._tried_hypothesis_titles),
            "final_analysis": final_analysis,
            "all_analyses": self.analyses,
            "all_results": self.prior_results,
        }

    def get_research_history(self) -> Dict[str, Any]:
        """Return a structured summary of the research history.

        Returns:
            Dictionary containing the complete research history.
        """
        return {
            "objective": self.objective.model_dump(),
            "baseline": self.baseline,
            "iterations": self.iteration + 1,
            "hypotheses": [h.model_dump() for h in self.prior_hypotheses],
            "results": [r.model_dump() for r in self.prior_results],
            "evaluations": self.prior_evidence,
            "analyses": [a.model_dump() for a in self.analyses],
            "tried_experiment_types": list(self._tried_experiment_types),
            "tried_hypothesis_titles": list(self._tried_hypothesis_titles),
        }