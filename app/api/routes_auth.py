"""
Auth routes: register and login.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services.wallet_service import create_wallet_for_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user and auto-create a funded wallet."""
    hashed = hash_password(body.password)
    new_user = User(username=body.username, hashed_password=hashed)
    db.add(new_user)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already taken.")

    wallet = create_wallet_for_user(db, new_user.id)
    db.commit()

    return RegisterResponse(
        user_id=new_user.id,
        username=new_user.username,
        wallet_balance_bdt=str(wallet.balance),
        message="User registered and wallet funded with 100,000.00 BDT.",
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with username + password, return a JWT."""
    user = db.query(User).filter_by(username=body.username.lower()).first()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    access_token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=access_token)
