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
    from app.models.money_request import MoneyRequest
    # Incoming requests where this user is the payer
    incoming_objs = (
        db.query(MoneyRequest)
        .filter_by(payer_user_id=current_user.id)
        .order_by(MoneyRequest.created_at.desc())
        .all()
    )
    # Outgoing requests where this user is the requester
    outgoing_objs = (
        db.query(MoneyRequest)
        .filter_by(requester_user_id=current_user.id)
        .order_by(MoneyRequest.created_at.desc())
        .all()
    )

    all_user_ids = {r.requester_user_id for r in incoming_objs} | {r.payer_user_id for r in outgoing_objs}
    user_map = {u.id: u.username for u in db.query(User).filter(User.id.in_(all_user_ids)).all()} if all_user_ids else {}

    incoming = [
        {
            "request_id": r.id,
            "requester_username": user_map.get(r.requester_user_id, "Unknown"),
            "amount_bdt": str(r.amount_bdt),
            "note": r.note,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in incoming_objs
    ]

    outgoing = [
        {
            "request_id": r.id,
            "payer_username": user_map.get(r.payer_user_id, "Unknown"),
            "amount_bdt": str(r.amount_bdt),
            "note": r.note,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in outgoing_objs
    ]

    return {"incoming": incoming, "outgoing": outgoing}


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
