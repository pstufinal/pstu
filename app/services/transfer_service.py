"""
Transfer service: atomic money movement with double-entry ledger.

This is the most safety-critical module in the codebase. Every line here exists
because a payments bug is worse than a payments outage.
"""
import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.money import validate_amount
from app.models.transaction import IdempotencyRecord, LedgerEntry, Transaction
from app.models.user import User
from app.models.wallet import Wallet


def execute_transfer(
    db: Session,
    sender_user_id: int,
    recipient_username: str,
    amount_bdt: Decimal,
    idempotency_key: str,
    note: str | None = None,
) -> dict:
    """
    Why one DB transaction for the whole transfer: partial state (money debited
    but not credited) is the worst possible bug in a payments system. PostgreSQL's
    ACID guarantees all-or-nothing.

    Why lock in ascending wallet-ID order: if Alice→Bob locks [alice, bob] and
    Bob→Alice locks [bob, alice] at the same time, they deadlock. Sorting by ID
    gives a global lock order that makes deadlock *impossible*.
    """
    validate_amount(amount_bdt)

    # ── Idempotency fast path ─────────────────────────────────────────────────
    # Why check before locking: avoids acquiring expensive row locks for retried
    # requests that were already completed.
    existing_record = db.query(IdempotencyRecord).filter_by(
        idempotency_key=idempotency_key
    ).first()
    if existing_record:
        return json.loads(existing_record.response_payload)

    # ── Resolve sender and recipient ──────────────────────────────────────────
    sender_user = db.query(User).filter_by(id=sender_user_id).first()
    if sender_user is None:
        raise HTTPException(status_code=401, detail="Sender not found.")

    recipient_user = db.query(User).filter_by(username=recipient_username).first()
    if recipient_user is None:
        raise HTTPException(status_code=404, detail="Recipient not found.")

    if sender_user.id == recipient_user.id:
        raise HTTPException(status_code=400, detail="Cannot send money to yourself.")

    # ── Locate wallets (unlocked read first, for validation) ──────────────────
    sender_wallet = db.query(Wallet).filter_by(user_id=sender_user.id).first()
    recipient_wallet = db.query(Wallet).filter_by(user_id=recipient_user.id).first()

    if sender_wallet is None or recipient_wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    # ── Lock wallets in ascending ID order to prevent deadlocks ───────────────
    # Why two separate SELECTs instead of one IN query: guarantees lock acquisition
    # order. A single SELECT ... WHERE id IN (...) ORDER BY id FOR UPDATE may not
    # acquire locks in the ORDER BY sequence because the planner can pick any index
    # scan order. Two sequential SELECTs are deterministic.
    wallet_ids_sorted = sorted([sender_wallet.id, recipient_wallet.id])
    first_locked = (
        db.query(Wallet)
        .filter_by(id=wallet_ids_sorted[0])
        .with_for_update()
        .first()
    )
    second_locked = (
        db.query(Wallet)
        .filter_by(id=wallet_ids_sorted[1])
        .with_for_update()
        .first()
    )

    # Map back to sender / recipient after locking.
    if first_locked.id == sender_wallet.id:
        sender_wallet_locked = first_locked
        recipient_wallet_locked = second_locked
    else:
        sender_wallet_locked = second_locked
        recipient_wallet_locked = first_locked

    # ── Validate balance ──────────────────────────────────────────────────────
    if sender_wallet_locked.balance < amount_bdt:
        raise HTTPException(status_code=400, detail="Insufficient balance.")

    # ── Update balances atomically ────────────────────────────────────────────
    sender_wallet_locked.balance -= amount_bdt
    recipient_wallet_locked.balance += amount_bdt

    # ── Create transaction record ─────────────────────────────────────────────
    transaction = Transaction(
        sender_wallet_id=sender_wallet_locked.id,
        recipient_wallet_id=recipient_wallet_locked.id,
        amount_bdt=amount_bdt,
        note=note,
        idempotency_key=idempotency_key,
    )
    db.add(transaction)
    # Why flush here: we need transaction.id for the ledger entries, but we
    # haven't committed yet — the whole thing is still one atomic DB transaction.
    db.flush()

    # ── Double-entry ledger: 1 transaction → 2 ledger entries ─────────────────
    # Why double-entry: if SUM(credits) ≠ SUM(debits), we know data is corrupt.
    # Single-entry bookkeeping cannot detect this class of bug.
    debit_entry = LedgerEntry(
        transaction_id=transaction.id,
        wallet_id=sender_wallet_locked.id,
        entry_type="DEBIT",
        amount_bdt=amount_bdt,
        balance_after=sender_wallet_locked.balance,
    )
    credit_entry = LedgerEntry(
        transaction_id=transaction.id,
        wallet_id=recipient_wallet_locked.id,
        entry_type="CREDIT",
        amount_bdt=amount_bdt,
        balance_after=recipient_wallet_locked.balance,
    )
    db.add_all([debit_entry, credit_entry])

    # ── Build response payload ────────────────────────────────────────────────
    response_data = {
        "transaction_id": transaction.id,
        "sender": sender_user.username,
        "recipient": recipient_user.username,
        "amount_bdt": str(amount_bdt.quantize(Decimal("0.01"))),
        "note": note,
        "status": "completed",
    }

    # ── Store idempotency record ──────────────────────────────────────────────
    # Why store the serialised response: on replay we return the *exact* same
    # payload, so the caller cannot distinguish a replay from the original.
    idempotency_record = IdempotencyRecord(
        idempotency_key=idempotency_key,
        user_id=sender_user_id,
        response_payload=json.dumps(response_data),
    )
    db.add(idempotency_record)

    # ── Commit: the entire transfer is atomic ─────────────────────────────────
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Why retry the read: another thread with the same idempotency key won
        # the commit race. We return *their* cached response instead of erroring.
        existing_record = db.query(IdempotencyRecord).filter_by(
            idempotency_key=idempotency_key
        ).first()
        if existing_record:
            return json.loads(existing_record.response_payload)
        # Not an idempotency collision — some other constraint failed.
        raise HTTPException(status_code=409, detail="Transfer conflict. Please retry.")

    return response_data
