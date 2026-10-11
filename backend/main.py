from fastapi import FastAPI
from backend.axiom.api.routes import build_router, ServiceState
from backend.axiom.config import Settings
from dotenv import load_dotenv

# Load project-local configuration before constructing Settings. Existing shell
# environment variables keep precedence over values from .env.
load_dotenv(override=False)

settings = Settings()
app = FastAPI(title=settings.app_name)
state = ServiceState(settings)
app.include_router(build_router(state))


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.app_name} API"}

