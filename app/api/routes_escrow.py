"""
API routes for Escrow payments.
"""
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db, get_read_db
from app.models.escrow import EscrowPayment
from app.models.user import User
from app.schemas.escrow import EscrowCreate, EscrowResponse
from app.services.escrow_service import cancel_payment, hold_payment, release_payment

router = APIRouter(prefix="/escrow", tags=["escrow"])


@router.post("/payments", response_model=EscrowResponse)
def create_escrow_payment(
    request: EscrowCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Hold funds in escrow for a transaction.
    """
    return hold_payment(
        db=db,
        buyer_user=current_user,
        seller_username=request.seller_username,
        amount_bdt=request.amount_bdt,
        idempotency_key=idempotency_key,
        note=request.note,
    )


@router.post("/payments/{id}/release", response_model=EscrowResponse)
def release_escrow_payment(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Release escrow funds to the seller. Only the buyer can do this.
    """
    return release_payment(db=db, buyer_user=current_user, escrow_id=id)


@router.post("/payments/{id}/cancel", response_model=EscrowResponse)
def cancel_escrow_payment(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel escrow payment and refund buyer. Only the buyer can do this.
    """
    return cancel_payment(db=db, buyer_user=current_user, escrow_id=id)


@router.get("/payments", response_model=list[EscrowResponse])
def get_escrow_payments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_read_db),
):
    """
    Get all escrow payments where the user is either buyer or seller.
    """
    payments = (
        db.query(EscrowPayment)
        .filter(
            (EscrowPayment.buyer_user_id == current_user.id)
            | (EscrowPayment.seller_user_id == current_user.id)
        )
        .order_by(EscrowPayment.created_at.desc())
        .all()
    )
    return payments
