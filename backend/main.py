"""FastAPI application entry point for AXIOM."""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.axiom.api.routes import ServiceState, build_router
from backend.axiom.config import Settings


def _cors_origins_from_env() -> list[str]:
    """Read trusted browser origins from a comma-separated environment variable.

    Local Next.js development origins are allowed by default. Deployments should
    set AXIOM_CORS_ORIGINS to the exact frontend origins they trust.
    """
    raw = os.environ.get(
        "AXIOM_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


# Load project-local configuration before constructing Settings. Existing shell
# environment variables keep precedence over values from .env.
load_dotenv(override=False)

settings = Settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_from_env(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

state = ServiceState(settings)
app.include_router(build_router(state))


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.app_name} API"}
