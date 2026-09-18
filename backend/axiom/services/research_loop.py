from __future__ import annotations

from pydantic import BaseModel, Field

from axiom.agents.analyst import AnalystAgent
from axiom.agents.planner import PlannerAgent
from axiom.agents.researcher import ResearcherAgent
from axiom.config import Settings
from axiom.domain.interfaces import (
    ExperimentEvaluator,
    ExperimentExecutor,
    MemoryRepository,
    ProviderError,
    ReasoningProvider,
)
from axiom.domain.models import ExperimentSpec, LoopSummary, ResearchObjective, RunStatus
from axiom.execution.artifacts import ArtifactStore
from axiom.execution.evaluator import DeterministicEvaluator
from axiom.execution.local_executor import LocalExecutor
from axiom.memory.sqlite_repo import SqliteRepository
from axiom.providers.echo_provider import EchoReasoningProvider


class ResearchLoopConfig(BaseModel):
    max_iterations: int = Field(default=5, ge=1, le=100)
    baseline_timeout_seconds: float = Field(default=120.0, gt=0)


class LoopServices:
    def __init__(
        self,
        *,
        provider: ReasoningProvider,
        researcher: ResearcherAgent,
        planner: PlannerAgent,
        analyst: AnalystAgent,
        executor: ExperimentExecutor,
        evaluator: ExperimentEvaluator,
        repository: MemoryRepository,
        artifact_store: ArtifactStore,
    ) -> None:
        self.provider = provider
        self.researcher = researcher
        self.planner = planner
        self.analyst = analyst
        self.executor = executor
        self.evaluator = evaluator
        self.repository = repository
        self.artifact_store = artifact_store

    @classmethod
    def from_settings(cls, settings: Settings) -> LoopServices:
        if settings.reasoning_provider != "echo":
            raise RuntimeError(f"Unsupported reasoning provider: {settings.reasoning_provider}")
        provider = EchoReasoningProvider()
        artifact_store = ArtifactStore(root=settings.artifact_root)
        return cls(
            provider=provider,
            researcher=ResearcherAgent(provider),
            planner=PlannerAgent(provider),
            analyst=AnalystAgent(provider),
            executor=LocalExecutor(artifact_store=artifact_store),
            evaluator=DeterministicEvaluator(),
            repository=SqliteRepository(db_path=settings.db_path),
            artifact_store=artifact_store,
        )


class ResearchLoopService:
    def __init__(self, services: LoopServices, config: ResearchLoopConfig) -> None:
        self.services = services
        self.config = config

    def run_objective(self, objective: ResearchObjective) -> LoopSummary:
        self.services.repository.save_objective(objective)
        last_summary = LoopSummary(iteration=0, objective=objective, stopped=True, stop_reason="max_iterations")
        for _ in range(self.config.max_iterations):
            iteration = self.services.repository.next_hypothesis_number(objective.id)
            try:
                hypothesis = self.services.researcher.propose(
                    objective,
                    iteration=iteration,
                    prior_evidence_summary=self._prior_summary(objective.id),
                )
            except ProviderError as exc:
                raise RuntimeError(f"Researcher failed: {exc}") from exc
            self.services.repository.save_hypothesis(hypothesis)
            try:
                plan, spec_candidate = self.services.planner.design(hypothesis, objective)
            except ProviderError as exc:
                raise RuntimeError(f"Planner failed: {exc}") from exc
            if objective.metric not in plan.metrics:
                raise RuntimeError(f"Plan metrics {plan.metrics} missing objective metric {objective.metric}")
            self.services.repository.save_plan(plan)
            self.services.repository.save_spec(spec_candidate)
            spec_baseline = ExperimentSpec(
                plan_id=plan.id,
                name=f"{hypothesis.id}-baseline",
                description=spec_candidate.description,
                code=spec_candidate.code,
                parameters=spec_candidate.parameters,
                environment={**spec_candidate.environment, "__AXIOM_LEVER_MODE__": "baseline"},
            )
            self.services.repository.save_spec(spec_baseline)
            baseline_run = self.services.executor.execute(spec_baseline, plan.timeout_seconds)
            candidate_run = self.services.executor.execute(spec_candidate, plan.timeout_seconds)
            self.services.repository.save_run(baseline_run)
            self.services.repository.save_run(candidate_run)
            run_ids = [baseline_run.id, candidate_run.id]
            if baseline_run.status != RunStatus.COMPLETED or candidate_run.status != RunStatus.COMPLETED:
                last_summary = LoopSummary(
                    iteration=iteration,
                    objective=objective,
                    hypothesis=hypothesis,
                    plan=plan,
                    spec=spec_candidate,
                    run_ids=run_ids,
                    target_met=False,
                    stopped=False,
                    stop_reason=None,
                )
                continue
            evaluation = self.services.evaluator.evaluate(
                baseline=baseline_run,
                candidate=candidate_run,
                plan=plan,
                objective=objective,
            )
            self.services.repository.save_evaluation(evaluation)
            try:
                evidence = self.services.analyst.analyze(evaluation, hypothesis, objective)
            except ProviderError as exc:
                raise RuntimeError(f"Analyst failed: {exc}") from exc
            self.services.repository.save_evidence(evidence)
            if evaluation.target_met:
                return LoopSummary(
                    iteration=iteration,
                    objective=objective,
                    hypothesis=hypothesis,
                    plan=plan,
                    spec=spec_candidate,
                    run_ids=run_ids,
                    evaluation=evaluation,
                    evidence=evidence,
                    target_met=True,
                    stopped=True,
                    stop_reason="target_met",
                )
            last_summary = LoopSummary(
                iteration=iteration,
                objective=objective,
                hypothesis=hypothesis,
                plan=plan,
                spec=spec_candidate,
                run_ids=run_ids,
                evaluation=evaluation,
                evidence=evidence,
                target_met=False,
                stopped=False,
                stop_reason=None,
            )
        last_summary.stopped = True
        if last_summary.stop_reason is None:
            last_summary.stop_reason = "max_iterations"
        return last_summary

    def _prior_summary(self, objective_id: str) -> str:
        parts: list[str] = []
        for history in self.services.repository.history_for_objective(objective_id)[-3:]:
            if history.evidence is not None:
                parts.append(f"{history.hypothesis.statement} -> {history.evidence.conclusion}")
            else:
                parts.append(history.hypothesis.statement)
        return "; ".join(parts)
