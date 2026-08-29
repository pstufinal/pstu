"""
Money-request routes: create, approve, reject.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.money_request import MoneyRequestCreate
from app.services.request_service import (
    approve_money_request,
    create_money_request,
    reject_money_request,
)

router = APIRouter(prefix="/money-requests", tags=["money-requests"])


@router.get("")
def get_user_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all incoming and outgoing money requests for the authenticated user."""
    from app.services.request_service import list_user_requests
    return list_user_requests(db=db, user_id=current_user.id)


@router.post("")
def create_request(
    body: MoneyRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a money request asking another user to pay you."""
    return create_money_request(
        db=db,
        requester_user_id=current_user.id,
        payer_username=body.payer_username,
        amount_bdt=body.amount_bdt,
        note=body.note,
    )


@router.post("/{request_id}/approve")
def approve_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve a money request (only the payer can do this)."""
    return approve_money_request(
        db=db,
        request_id=request_id,
        approver_user_id=current_user.id,
    )


@router.post("/{request_id}/reject")
def reject_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject a money request (only the payer can do this)."""
    return reject_money_request(
        db=db,
        request_id=request_id,
        rejector_user_id=current_user.id,
    )
