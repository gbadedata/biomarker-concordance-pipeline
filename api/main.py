"""FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, get_db
from .models import Base
from .routers import alerts, concordance, health, reproducibility, runs

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("api_startup")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_schema_ready")
    yield
    await engine.dispose()
    logger.info("api_shutdown")


app = FastAPI(
    title="Biomarker Concordance API",
    description="REST API for the biomarker concordance pipeline.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inject db dependency into all routers
for mod in [health, runs, concordance, reproducibility, alerts]:
    mod.get_db = get_db  # type: ignore[attr-defined]

app.include_router(health.router,          prefix="/health",                    tags=["health"])
app.include_router(runs.router,            prefix="/api/v1/runs",               tags=["runs"])
app.include_router(concordance.router,     prefix="/api/v1/concordance",        tags=["concordance"])
app.include_router(reproducibility.router, prefix="/api/v1/reproducibility",    tags=["reproducibility"])
app.include_router(alerts.router,          prefix="/api/v1/alerts",             tags=["alerts"])
