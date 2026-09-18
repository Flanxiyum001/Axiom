from typing import List, Dict, Optional, Any
from ..models.schemas import (
    ExperimentResult,
    Hypothesis,
    ExperimentPlan,
    Analysis,
    ResearchObjective,
)
from uuid import UUID


class ResearchMemoryStore:
    """Structured in-memory store for AXIOM research artifacts.

    Stores objectives, hypotheses, experiment plans, experiment results,
    evaluation results, and analyst observations so the next Researcher
    call can see what has already been tried.

    No vector database is used - a simple structured in-memory store is
    sufficient for Phase 3.
    """

    def __init__(self):
        self._objectives: Dict[UUID, ResearchObjective] = {}
        self._hypotheses: Dict[UUID, Hypothesis] = {}
        self._plans: Dict[UUID, ExperimentPlan] = {}
        self._results: Dict[UUID, ExperimentResult] = {}
        self._evaluations: Dict[UUID, Dict[str, Any]] = {}
        self._analyses: Dict[UUID, Analysis] = {}

    def save_objective(self, objective: ResearchObjective) -> None:
        self._objectives[objective.id] = objective

    def get_objective(self, objective_id: UUID) -> Optional[ResearchObjective]:
        return self._objectives.get(objective_id)

    def list_objectives(self) -> List[ResearchObjective]:
        return list(self._objectives.values())

    def save_hypothesis(self, hypothesis: Hypothesis) -> None:
        self._hypotheses[hypothesis.id] = hypothesis

    def get_hypothesis(self, hypothesis_id: UUID) -> Optional[Hypothesis]:
        return self._hypotheses.get(hypothesis_id)

    def list_hypotheses(self, objective_id: Optional[UUID] = None) -> List[Hypothesis]:
        hypotheses = list(self._hypotheses.values())
        if objective_id is not None:
            hypotheses = [h for h in hypotheses if h.objective_id == objective_id]
        return hypotheses

    def save_plan(self, plan: ExperimentPlan) -> None:
        self._plans[plan.id] = plan

    def get_plan(self, plan_id: UUID) -> Optional[ExperimentPlan]:
        return self._plans.get(plan_id)

    def list_plans(self, hypothesis_id: Optional[UUID] = None) -> List[ExperimentPlan]:
        plans = list(self._plans.values())
        if hypothesis_id is not None:
            plans = [p for p in plans if p.hypothesis_id == hypothesis_id]
        return plans

    def save_result(self, result: ExperimentResult) -> None:
        self._results[result.experiment_id] = result

    def get_result(self, experiment_id: UUID) -> Optional[ExperimentResult]:
        return self._results.get(experiment_id)

    def list_all_results(self) -> List[ExperimentResult]:
        return list(self._results.values())

    def get_successful_experiments(self) -> List[ExperimentResult]:
        return [r for r in self._results.values() if r.status == "completed"]

    def get_failed_experiments(self) -> List[ExperimentResult]:
        return [r for r in self._results.values() if r.status == "failed"]

    def save_evaluation(self, experiment_id: UUID, evaluation: Dict[str, Any]) -> None:
        self._evaluations[experiment_id] = evaluation

    def get_evaluation(self, experiment_id: UUID) -> Optional[Dict[str, Any]]:
        return self._evaluations.get(experiment_id)

    def list_all_evaluations(self) -> List[Dict[str, Any]]:
        return list(self._evaluations.values())

    def save_analysis(self, analysis: Analysis) -> None:
        self._analyses[analysis.id] = analysis

    def get_analysis(self, analysis_id: UUID) -> Optional[Analysis]:
        return self._analyses.get(analysis_id)

    def list_analyses(self, experiment_id: Optional[UUID] = None) -> List[Analysis]:
        analyses = list(self._analyses.values())
        if experiment_id is not None:
            analyses = [a for a in analyses if a.experiment_id == experiment_id]
        return analyses

    def get_research_context(self, objective_id: Optional[UUID] = None) -> Dict[str, List[Any]]:
        """Return all stored research context for the next Researcher call."""
        return {
            "hypotheses": self.list_hypotheses(objective_id),
            "plans": self.list_plans(),
            "results": self.list_all_results(),
            "evaluations": self.list_all_evaluations(),
            "analyses": self.list_analyses(),
        }
