"""FastAPI application entry point."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..storage.cache import redis_client
from ..utils.logger import logger
from ..utils.workspace import workspace_manager
from .routes import health, research, settings, stream


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler."""
    # Startup
    logger.info("application_startup")
    workspace_manager.initialize()
    await redis_client.connect()

    yield

    # Shutdown
    logger.info("application_shutdown")
    await redis_client.disconnect()


# Create FastAPI application
app = FastAPI(
    title="AutoResearch Agent System",
    description="Multi-agent automated research and writing system",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware - configurable for security
# For production, restrict to specific domains via environment variable
_cors_origins = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else ["http://localhost:3000", "http://localhost:8000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(stream.router, prefix="/api/research", tags=["stream"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])


@app.get("/")
async def root():
    """Root endpoint - serve frontend."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "index.html")
    return FileResponse(frontend_path, media_type="text/html")


# Mount static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
