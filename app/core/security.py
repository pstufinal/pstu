"""
Authentication utilities: password hashing and JWT token management.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db


# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """Why bcrypt: adaptive cost factor makes brute-force infeasible even if DB is leaked."""
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Why bcrypt.checkpw: constant-time comparison prevents timing attacks."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ── JWT tokens ─────────────────────────────────────────────────────────────────

def create_access_token(user_id: int, username: str) -> str:
    """Why short expiry: limits blast radius if a token is intercepted on the wire."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(user_id), "username": username, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Why single decode function: one audit point for all token validation logic."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


# ── FastAPI dependency: extract current user from Bearer token ────────────────

_bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
):
    """
    Why a dependency, not middleware: gives each route explicit opt-in to auth,
    and makes the User object directly injectable into route signatures.
    """
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token: missing subject.")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    # Lazy import to avoid circular dependency (security -> models -> database -> ...)
    from app.models.user import User

    user = db.query(User).filter_by(id=int(user_id)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found.")
    return user
