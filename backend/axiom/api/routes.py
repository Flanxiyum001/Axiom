"""FastAPI routes for the AXIOM API.

Exposes the research loop over HTTP. All request/response bodies are typed
Pydantic models derived from domain objects - no arbitrary dictionaries.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from axiom.config import Settings
from axiom.domain.models import LoopSummary, ResearchHistory, ResearchObjective
from axiom.services.objective_parser import ObjectiveParseError, parse_objective
from axiom.services.research_loop import (
    LoopServices,
    ResearchLoopConfig,
    ResearchLoopService,
)

logger = logging.getLogger("axiom.api")


class CreateObjectiveRequest(BaseModel):
    description: str = Field(min_length=3, examples=["Reduce model inference latency by 20%"])
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
        self._services: LoopServices | None = None

    def services(self) -> LoopServices:
        if self._services is None:
            self._services = LoopServices.from_settings(self.settings)
        return self._services


def build_router(state: ServiceState) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "provider": state.settings.reasoning_provider}

    @router.post("/objectives", status_code=201)
    def create_objective(request: CreateObjectiveRequest) -> ObjectiveCreatedResponse:
        """Parse and persist an objective without running the loop."""
        try:
            objective = parse_objective(request.description)
        except ObjectiveParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        state.services().repository.save_objective(objective)
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
    def run_objective(objective_id: str, request: RunObjectiveRequest) -> ResearchRunResponse:
        objective = state.services().repository.get_objective(objective_id)
        if objective is None:
            raise HTTPException(status_code=404, detail="objective not found")
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

    @router.post("/research")
    def run_research(request: CreateObjectiveRequest) -> ResearchRunResponse:
        """One-shot: parse an objective and run the full loop."""
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
