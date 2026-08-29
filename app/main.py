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
from app.api.routes_escrow import router as escrow_router
from app.api.routes_requests import router as request_router
from app.api.routes_scaling import router as scaling_router
from app.api.routes_transfers import router as transfer_router
from app.api.routes_verify import router as verify_router
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Why startup logic here: guarantees tables exist before the first request,
    preventing 500 errors on cold starts.
    """
    Base.metadata.create_all(bind=engine)
    
    # ── Escrow Startup Migrations & Setup ─────────────────────────────────────
    from sqlalchemy import text
    from decimal import Decimal
    from app.database import SessionLocal
    from app.models.user import User
    from app.models.wallet import Wallet
    from app.core.security import hash_password

    db = SessionLocal()
    try:
        # Safe raw SQL migration for the type column since we don't have Alembic
        db.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS type VARCHAR(20) DEFAULT 'TRANSFER' NOT NULL;"))
        db.commit()
        
        # ── Safe raw SQL migration for trx_code ──
        db.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS trx_code VARCHAR(15);"))
        db.commit()
        
        from app.models.transaction import Transaction
        from app.utils.trx import generate_trx_code
        
        # Backfill null trx_code rows
        unmigrated_txs = db.query(Transaction).filter(Transaction.trx_code.is_(None)).all()
        if unmigrated_txs:
            for tx in unmigrated_txs:
                tx.trx_code = generate_trx_code()
            db.commit()
        
        # Add constraints
        db.execute(text("ALTER TABLE transactions ADD CONSTRAINT uq_trx_code UNIQUE (trx_code);"))
        db.execute(text("ALTER TABLE transactions ALTER COLUMN trx_code SET NOT NULL;"))
        db.commit()
    except Exception as e:
        db.rollback()
        
    try:
        # Ensure ESCROW_HOLD user exists
        escrow_sys = db.query(User).filter_by(username="ESCROW_HOLD").first()
        if not escrow_sys:
            escrow_sys = User(username="ESCROW_HOLD", hashed_password=hash_password("system_no_login"))
            db.add(escrow_sys)
            db.flush()
            sys_wallet = Wallet(user_id=escrow_sys.id, balance=Decimal("0.00"))
            db.add(sys_wallet)
            db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

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
app.include_router(scaling_router)
app.include_router(escrow_router)
app.include_router(verify_router)


@app.get("/health")
def health_check():
    """Liveness probe for monitoring."""
    return {"status": "healthy"}


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


# ── Mount static files for Web UI (must be last to allow API routes to match first) ───
import os
from fastapi.staticfiles import StaticFiles

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

