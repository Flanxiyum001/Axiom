from fastapi import FastAPI, HTTPException
from typing import List, Dict
from uuid import UUID
from .config import settings
from .models.schemas import ResearchObjective, ExperimentResult, MetricDefinition, MetricDirection
from .orchestrator import Orchestrator

app = FastAPI(title=settings.app_name)

# In-memory storage for the MVP
objectives: Dict[UUID, ResearchObjective] = {}
orchestrators: Dict[UUID, Orchestrator] = {}

@app.get("/health")
async def health():
    return {"status": "healthy", "app": settings.app_name}

@app.post("/research", response_model=ResearchObjective)
async def create_research(objective: ResearchObjective):
    objectives[objective.id] = objective
    # Initialize orchestrator with a mock baseline for now
    # In a real scenario, the baseline would be the first experiment
    baseline = {"latency_ms": 142.0, "accuracy": 0.914}
    orchestrators[objective.id] = Orchestrator(objective, baseline)
    return objective

@app.post("/research/{research_id}/run")
async def run_research(research_id: UUID):
    if research_id not in orchestrators:
        raise HTTPException(status_code=404, detail="Research objective not found")
    
    orchestrator = orchestrators[research_id]
    orchestrator.run_loop()
    return {"message": "Research loop completed"}

@app.get("/research/{research_id}", response_model=ResearchObjective)
async def get_research(research_id: UUID):
    if research_id not in objectives:
        raise HTTPException(status_code=404, detail="Research objective not found")
    return objectives[research_id]

@app.get("/research/{research_id}/experiments", response_model=List[ExperimentResult])
async def get_research_experiments(research_id: UUID):
    if research_id not in orchestrators:
        raise HTTPException(status_code=404, detail="Research objective not found")
    return orchestrators[research_id].store.list_all_results()

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.app_name} API"}
