"""
Escrow payment services.
"""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.escrow import EscrowPayment
from app.models.user import User
from app.services.transfer_service import execute_transfer

ESCROW_USERNAME = "ESCROW_HOLD"


def get_escrow_hold_user(db: Session) -> User:
    user = db.query(User).filter_by(username=ESCROW_USERNAME).first()
    if not user:
        raise HTTPException(status_code=500, detail="Escrow system not initialized.")
    return user


def hold_payment(
    db: Session,
    buyer_user: User,
    seller_username: str,
    amount_bdt: Decimal,
    idempotency_key: str,
    note: str | None = None,
) -> EscrowPayment:
    """
    Why hold payment: locks funds in a central escrow wallet, providing
    trust for both buyer and seller.
    """
    # 1. Fast path idempotency check for EscrowPayment creation
    existing_escrow = db.query(EscrowPayment).filter_by(idempotency_key=idempotency_key).first()
    if existing_escrow:
        return existing_escrow

    seller_user = db.query(User).filter_by(username=seller_username).first()
    if not seller_user:
        raise HTTPException(status_code=404, detail="Seller not found.")

    if seller_user.id == buyer_user.id:
        raise HTTPException(status_code=400, detail="Cannot escrow to yourself.")

    # We add the EscrowPayment row to the session.
    # The subsequent execute_transfer will commit it atomically alongside the transfer.
    escrow = EscrowPayment(
        buyer_user_id=buyer_user.id,
        seller_user_id=seller_user.id,
        amount=amount_bdt,
        status="HELD",
        idempotency_key=idempotency_key,
        note=note,
    )
    db.add(escrow)

    # Move money: buyer -> ESCROW_HOLD
    # This function commits the session!
    execute_transfer(
        db=db,
        sender_user_id=buyer_user.id,
        recipient_username=ESCROW_USERNAME,
        idempotency_key=f"hold_{idempotency_key}",
        amount_bdt=amount_bdt,
        note=f"Escrow hold for {seller_username}: {note}",
        transaction_type="ESCROW_HOLD",
    )

    # After commit, the escrow object is refreshed
    return escrow


def release_payment(db: Session, buyer_user: User, escrow_id: int) -> EscrowPayment:
    """
    Why release payment: only the buyer can release, and only if HELD.
    Locks the escrow row to prevent concurrent release/cancel races.
    """
    # Lock the escrow row FOR UPDATE
    escrow = (
        db.query(EscrowPayment)
        .filter_by(id=escrow_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow payment not found.")

    if escrow.buyer_user_id != buyer_user.id:
        # Seller cannot release or cancel
        raise HTTPException(status_code=403, detail="Only the buyer can modify this escrow.")

    if escrow.status != "HELD":
        raise HTTPException(status_code=409, detail=f"Escrow is already {escrow.status}.")

    seller_user = db.query(User).filter_by(id=escrow.seller_user_id).first()
    escrow_sys_user = get_escrow_hold_user(db)

    # Update status
    escrow.status = "RELEASED"
    escrow.decided_at = datetime.now(timezone.utc)

    # Execute transfer: ESCROW_HOLD -> seller
    # The execute_transfer will commit the escrow status update atomically
    execute_transfer(
        db=db,
        sender_user_id=escrow_sys_user.id,
        recipient_username=seller_user.username,
        idempotency_key=f"release_{escrow.id}_{escrow.idempotency_key}",
        amount_bdt=escrow.amount,
        note=f"Escrow released for ID {escrow.id}",
        transaction_type="ESCROW_RELEASE",
    )

    return escrow


def cancel_payment(db: Session, buyer_user: User, escrow_id: int) -> EscrowPayment:
    """
    Why cancel payment: refunds the buyer if the seller fails to deliver.
    """
    escrow = (
        db.query(EscrowPayment)
        .filter_by(id=escrow_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow payment not found.")

    if escrow.buyer_user_id != buyer_user.id:
        raise HTTPException(status_code=403, detail="Only the buyer can modify this escrow.")

    if escrow.status != "HELD":
        raise HTTPException(status_code=409, detail=f"Escrow is already {escrow.status}.")

    escrow_sys_user = get_escrow_hold_user(db)

    # Update status
    escrow.status = "REFUNDED"
    escrow.decided_at = datetime.now(timezone.utc)

    # Execute transfer: ESCROW_HOLD -> buyer
    execute_transfer(
        db=db,
        sender_user_id=escrow_sys_user.id,
        recipient_username=buyer_user.username,
        idempotency_key=f"cancel_{escrow.id}_{escrow.idempotency_key}",
        amount_bdt=escrow.amount,
        note=f"Escrow refunded for ID {escrow.id}",
        transaction_type="ESCROW_REFUND",
    )

    return escrow
