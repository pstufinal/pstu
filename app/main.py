"""
FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Why import models before create_all: SQLAlchemy only knows about tables that
# have been imported and registered with Base.metadata.
import app.models  # noqa: F401 — triggers model registration

from app.api.routes_auth import router as auth_router
from app.api.routes_requests import router as request_router
from app.api.routes_transfers import router as transfer_router
from app.database import Base, engine


@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Why create_all in lifespan, not at module level: allows importing the app
    module (for tests, tooling) without requiring a live DB connection.
    In production, use Alembic migrations for schema versioning.
    """
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Money Movement API",
    description="PSTU Hackathon — peer-to-peer money transfer with double-entry ledger",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Register routers ─────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(transfer_router)
app.include_router(request_router)


# ── Global exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Why catch-all handler: never leak stack traces to end users. A 500 with
    debug info is an information disclosure vulnerability (CWE-209).
    """
    # Log the real error server-side (visible in uvicorn console).
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )


@app.get("/health")
def health_check():
    """Liveness probe for monitoring."""
    return {"status": "healthy"}
