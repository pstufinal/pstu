"""
Money-request service: create, approve, and reject payment requests.

Approval reuses execute_transfer so there is exactly one code path that
moves money — no risk of divergence between "send" and "approve" logic.
"""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.money import validate_amount
from app.models.money_request import MoneyRequest
from app.models.user import User
from app.services.transfer_service import execute_transfer


def create_money_request(
    db: Session,
    requester_user_id: int,
    payer_username: str,
    amount_bdt: Decimal,
    note: str | None = None,
) -> dict:
    """
    Why separate from transfers: a request is a *proposal*, not a movement of
    money. No wallet locks are needed because no balances change until approval.
    """
    validate_amount(amount_bdt)

    payer_user = db.query(User).filter_by(username=payer_username).first()
    if payer_user is None:
        raise HTTPException(status_code=404, detail="Payer not found.")

    if payer_user.id == requester_user_id:
        raise HTTPException(status_code=400, detail="Cannot request money from yourself.")

    requester_user = db.query(User).filter_by(id=requester_user_id).first()

    money_request = MoneyRequest(
        requester_user_id=requester_user_id,
        payer_user_id=payer_user.id,
        amount_bdt=amount_bdt,
        note=note,
        status="pending",
    )
    db.add(money_request)
    db.commit()

    return {
        "request_id": money_request.id,
        "requester": requester_user.username,
        "payer": payer_user.username,
        "amount_bdt": str(amount_bdt.quantize(Decimal("0.01"))),
        "note": note,
        "status": "pending",
    }


def approve_money_request(
    db: Session,
    request_id: int,
    approver_user_id: int,
) -> dict:
    """
    Why reuse execute_transfer: approval IS a transfer. Duplicating transfer
    logic would mean two code paths that can silently diverge — eventually one
    will have a bug the other doesn't.

    The money_request.status = 'approved' update lives in the same DB session
    as the transfer, so both commit atomically.
    """
    money_request = db.query(MoneyRequest).filter_by(id=request_id).first()
    if money_request is None:
        raise HTTPException(status_code=404, detail="Money request not found.")

    if money_request.payer_user_id != approver_user_id:
        raise HTTPException(
            status_code=403, detail="Only the payer can approve this request."
        )

    if money_request.status != "pending":
        raise HTTPException(
            status_code=400, detail=f"Request already {money_request.status}."
        )

    # Mark as approved. This dirty-flag sits in the same SQLAlchemy session,
    # so it will be committed atomically with the transfer below.
    money_request.status = "approved"

    requester_user = db.query(User).filter_by(
        id=money_request.requester_user_id
    ).first()

    # Why deterministic idempotency key from request_id: prevents double-transfer
    # if the approve endpoint is accidentally called twice.
    transfer_result = execute_transfer(
        db=db,
        sender_user_id=approver_user_id,
        recipient_username=requester_user.username,
        amount_bdt=money_request.amount_bdt,
        idempotency_key=f"money-request-{request_id}",
        note=money_request.note,
    )

    return {
        "request_id": request_id,
        "status": "approved",
        "transfer": transfer_result,
    }


def reject_money_request(
    db: Session,
    request_id: int,
    rejector_user_id: int,
) -> dict:
    """
    Why only the payer can reject: prevents the requester from cancelling
    their own request to hide evidence of a social-engineering attempt.
    """
    money_request = db.query(MoneyRequest).filter_by(id=request_id).first()
    if money_request is None:
        raise HTTPException(status_code=404, detail="Money request not found.")

    if money_request.payer_user_id != rejector_user_id:
        raise HTTPException(
            status_code=403, detail="Only the payer can reject this request."
        )

    if money_request.status != "pending":
        raise HTTPException(
            status_code=400, detail=f"Request already {money_request.status}."
        )

    money_request.status = "rejected"
    db.commit()

    return {
        "request_id": request_id,
        "status": "rejected",
        "message": "Money request rejected.",
    }


def list_user_requests(db: Session, user_id: int) -> dict:
    """
    Retrieve all incoming and outgoing money requests for the user.
    """
    # Incoming requests where this user is the payer
    incoming_objs = (
        db.query(MoneyRequest)
        .filter_by(payer_user_id=user_id)
        .order_by(MoneyRequest.created_at.desc())
        .all()
    )
    # Outgoing requests where this user is the requester
    outgoing_objs = (
        db.query(MoneyRequest)
        .filter_by(requester_user_id=user_id)
        .order_by(MoneyRequest.created_at.desc())
        .all()
    )

    # Collect user IDs to resolve usernames in bulk
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

