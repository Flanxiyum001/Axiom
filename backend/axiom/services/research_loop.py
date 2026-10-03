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
from axiom.execution import ExperimentEngine
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
        engine: ExperimentEngine | None = None,
    ) -> None:
        self.provider = provider
        self.researcher = researcher
        self.planner = planner
        self.analyst = analyst
        self.executor = executor
        self.evaluator = evaluator
        self.repository = repository
        self.artifact_store = artifact_store
        self.engine = engine or ExperimentEngine(executor=executor)

    @classmethod
    def from_settings(cls, settings: Settings) -> LoopServices:
        # Select the appropriate reasoning provider based on configuration.
        if settings.reasoning_provider == "echo":
            provider = EchoReasoningProvider()
        elif settings.reasoning_provider == "nebius":
            # Import lazily to avoid hard dependency when not used.
            from backend.llm.nebius import NebiusLLMProvider
            provider = NebiusLLMProvider(
                api_key=settings.nebius_api_key,
                base_url=settings.nebius_base_url,
                model=settings.nebius_model,
                request_timeout=settings.nebius_request_timeout,
                max_retries=settings.nebius_max_retries,
            )
        else:
            raise RuntimeError(f"Unsupported reasoning provider: {settings.reasoning_provider}")
        artifact_store = ArtifactStore(root=settings.artifact_root)
        executor = LocalExecutor(artifact_store=artifact_store)
        return cls(
            provider=provider,
            researcher=ResearcherAgent(provider),
            planner=PlannerAgent(provider),
            analyst=AnalystAgent(provider),
            executor=executor,
            evaluator=DeterministicEvaluator(),
            repository=SqliteRepository(db_path=settings.db_path),
            artifact_store=artifact_store,
            engine=ExperimentEngine(executor=executor),
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
            timeout = min(plan.timeout_seconds, self.config.baseline_timeout_seconds)
            result = self.services.engine.run(plan, spec_candidate, timeout)
            self.services.repository.save_spec(result.baseline_spec)
            self.services.repository.save_spec(result.candidate_spec)
            for run in result.individual_runs:
                self.services.repository.save_run(run)
            self.services.repository.save_run(result.baseline_run)
            self.services.repository.save_run(result.candidate_run)
            baseline_run = result.baseline_run
            candidate_run = result.candidate_run
            run_ids = [r.id for r in result.individual_runs] + [baseline_run.id, candidate_run.id]
            if baseline_run.status != RunStatus.COMPLETED or candidate_run.status != RunStatus.COMPLETED:
                last_summary = LoopSummary(
                    iteration=iteration,
                    objective=objective,
                    hypothesis=hypothesis,
                    plan=plan,
                    spec=result.candidate_spec,
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
                    spec=result.candidate_spec,
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
                spec=result.candidate_spec,
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
