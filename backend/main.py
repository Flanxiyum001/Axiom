from fastapi import FastAPI
from backend.axiom.api.routes import build_router, ServiceState
from backend.axiom.config import Settings

settings = Settings()
app = FastAPI(title=settings.app_name)
state = ServiceState(settings)
app.include_router(build_router(state))


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.app_name} API"}

