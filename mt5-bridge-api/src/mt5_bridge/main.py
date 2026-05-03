"""MT5 Bridge API — application entry point.

Startup sequence:
  1. Create (or verify) DB tables via SQLAlchemy metadata.
  2. Connect to the MetaTrader 5 terminal.

Shutdown sequence:
  1. Disconnect from MT5 and shut down the worker thread.
  2. Dispose of the SQLAlchemy async engine (closes the connection pool).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mt5_bridge.api.v1.router import router as v1_router
from mt5_bridge.config import settings
from mt5_bridge.metrics.otel import configure_otel
from mt5_bridge.models.db.base import Base
from mt5_bridge.services.mt5_connection import MT5Connection

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage the application lifecycle: DB pool + MT5 connection."""

    # ------------------------------------------------------------------ STARTUP
    logger.info("Starting MT5 Bridge API…")

    # Build the async SQLAlchemy engine and session factory.
    engine = create_async_engine(
        settings.db_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,   # validate connections before use
        pool_recycle=1_800,   # recycle connections every 30 min
    )
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.engine = engine

    # Ensure all ORM-managed tables exist (idempotent; does not run migrations).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified.")

    # Connect to the MT5 terminal in a worker thread (blocking call).
    mt5_conn = MT5Connection.get_instance(settings)
    await asyncio.to_thread(mt5_conn.connect)
    app.state.mt5_conn = mt5_conn

    yield  # ----------------------------------------- APPLICATION IS RUNNING

    # ----------------------------------------------------------------- SHUTDOWN
    logger.info("Shutting down MT5 Bridge API…")
    await asyncio.to_thread(mt5_conn.disconnect)
    await engine.dispose()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="MT5 Bridge API",
    description=(
        "Python service bridging FastAPI ↔ MetaTrader 5 (Exness). "
        "Exposes REST endpoints for account info, historical candles, and "
        "idempotent order management (open / close / modify)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# --- Prometheus instrumentation (exposes /metrics) ---
Instrumentator(
    excluded_handlers=["/metrics", "/health"],
    should_instrument_requests_inprogress=True,
).instrument(app).expose(app, include_in_schema=False)

# --- OpenTelemetry tracing ---
configure_otel(app, otel_endpoint=settings.otel_endpoint)

# --- API routers ---
app.include_router(v1_router)


# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------
@app.get("/health", include_in_schema=False, tags=["Ops"])
async def health() -> dict:
    """Simple liveness probe for load balancers and K8s readiness checks."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "mt5_bridge.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
