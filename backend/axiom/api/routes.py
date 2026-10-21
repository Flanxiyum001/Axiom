"""FastAPI routes for the AXIOM API.

Exposes the research loop over HTTP. All request/response bodies are typed
Pydantic models derived from domain objects - no arbitrary dictionaries.
"""

from __future__ import annotations

import logging

from axiom.api.demo_guard import DemoGuard
from axiom.config import Settings
from axiom.demo import DEMO_OBJECTIVE, validate_demo_configuration
from axiom.domain.models import LoopSummary, ResearchHistory, ResearchObjective
from axiom.services.objective_parser import ObjectiveParseError, parse_objective
from axiom.services.research_loop import (
    LoopServices,
    ResearchLoopConfig,
    ResearchLoopService,
)
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("axiom.api")


class CreateObjectiveRequest(BaseModel):
    description: str = Field(min_length=3, max_length=1000, examples=[DEMO_OBJECTIVE])
    max_iterations: int | None = Field(default=None, ge=1, le=100)


class RunObjectiveRequest(BaseModel):
    max_iterations: int | None = Field(default=None, ge=1, le=100)


class ObjectiveCreatedResponse(BaseModel):
    objective: ResearchObjective


class ResearchRunResponse(BaseModel):
    summary: LoopSummary


class ServiceState:
    """Process-wide API state (services built once per settings)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        if self.settings.demo_mode:
            validate_demo_configuration(self.settings)
        self.demo_guard = DemoGuard() if self.settings.demo_mode else None
        self._services: LoopServices | None = None

    def services(self) -> LoopServices:
        if self._services is None:
            self._services = LoopServices.from_settings(self.settings)
        return self._services


def build_router(state: ServiceState) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "provider": state.settings.reasoning_provider,
            "demo_mode": state.settings.demo_mode,
            "workload": "fixed_synthetic_cpu" if state.settings.demo_mode else "configured_executor",
        }

    @router.post("/objectives", status_code=201)
    def create_objective(request: CreateObjectiveRequest, http_request: Request) -> ObjectiveCreatedResponse:
        """Parse and persist an objective without running the loop."""
        if state.demo_guard and request.max_iterations not in (None, 1):
            raise HTTPException(status_code=422, detail="Demo allows one iteration per objective")
        try:
            objective = parse_objective(request.description)
        except ObjectiveParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        repository = state.services().repository
        if state.demo_guard:
            state.demo_guard.create_objective(http_request, repository, objective)
        else:
            repository.save_objective(objective)
        return ObjectiveCreatedResponse(objective=objective)

    @router.get("/objectives")
    def list_objectives() -> list[ResearchObjective]:
        return state.services().repository.list_objectives()

    @router.get("/objectives/{objective_id}")
    def get_objective(objective_id: str) -> ResearchObjective:
        objective = state.services().repository.get_objective(objective_id)
        if objective is None:
            raise HTTPException(status_code=404, detail="objective not found")
        return objective

    @router.get("/objectives/{objective_id}/history")
    def objective_history(objective_id: str) -> list[ResearchHistory]:
        if state.services().repository.get_objective(objective_id) is None:
            raise HTTPException(status_code=404, detail="objective not found")
        return state.services().repository.history_for_objective(objective_id)

    @router.post("/objectives/{objective_id}/run")
    def run_objective(
        objective_id: str, request: RunObjectiveRequest, http_request: Request
    ) -> ResearchRunResponse:
        if state.demo_guard and request.max_iterations not in (None, 1):
            raise HTTPException(status_code=422, detail="Demo allows one iteration per objective")
        objective = state.services().repository.get_objective(objective_id)
        if objective is None:
            raise HTTPException(status_code=404, detail="objective not found")
        services = state.services()
        config = ResearchLoopConfig(
            max_iterations=1 if state.demo_guard else request.max_iterations or state.settings.max_iterations,
            baseline_timeout_seconds=state.settings.run_timeout_seconds,
        )
        service = ResearchLoopService(services, config)
        if state.demo_guard:
            state.demo_guard.begin_run(http_request)
        try:
            if state.demo_guard and services.repository.history_for_objective(objective_id):
                raise HTTPException(status_code=409, detail="This demo objective has already been run")
            summary = service.run_objective(objective)
        except RuntimeError as exc:
            if state.demo_guard:
                logger.exception("Fixed demo run failed")
                raise HTTPException(status_code=502, detail="Fixed demo run failed") from exc
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        finally:
            if state.demo_guard:
                state.demo_guard.end_run()
        return ResearchRunResponse(summary=summary)

    @router.post("/research")
    def run_research(request: CreateObjectiveRequest) -> ResearchRunResponse:
        """One-shot: parse an objective and run the full loop."""
        if state.demo_guard:
            raise HTTPException(status_code=403, detail="One-shot research is disabled in demo mode")
        try:
            objective = parse_objective(request.description)
        except ObjectiveParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        state.services().repository.save_objective(objective)
        services = state.services()
        config = ResearchLoopConfig(
            max_iterations=request.max_iterations or state.settings.max_iterations,
            baseline_timeout_seconds=state.settings.run_timeout_seconds,
        )
        service = ResearchLoopService(services, config)
        try:
            summary = service.run_objective(objective)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return ResearchRunResponse(summary=summary)

    return router
