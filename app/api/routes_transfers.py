"""
Transfer and wallet routes: send money, check balance, view history.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_current_user
from app.database import get_db, get_read_db
from app.models.transaction import LedgerEntry
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.transfer import TransferRequest, TransferResponse
from app.services.transfer_service import execute_transfer

router = APIRouter(tags=["transfers"])


@router.post("/transfers/send", response_model=TransferResponse)
def send_money(
    body: TransferRequest,
    # Why Header dependency: FastAPI auto-converts underscores to hyphens and
    # matches case-insensitively, so this catches "Idempotency-Key" from curl.
    idempotency_key: str = Header(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send money to another user. Requires an Idempotency-Key header."""
    result = execute_transfer(
        db=db,
        sender_user_id=current_user.id,
        recipient_username=body.recipient_username,
        amount_bdt=body.amount_bdt,
        idempotency_key=idempotency_key,
        note=body.note,
    )
    return result


@router.get("/wallets/me")
def get_my_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_read_db),
):
    """Return the current user's wallet balance."""
    wallet = db.query(Wallet).filter_by(user_id=current_user.id).first()
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found.")
    return {
        "username": current_user.username,
        "balance_bdt": str(wallet.balance),
    }


@router.get("/transactions/history")
def get_transaction_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_read_db),
):
    """Return all ledger entries for the current user's wallet, newest first."""
    wallet = db.query(Wallet).filter_by(user_id=current_user.id).first()
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    ledger_entries = (
        db.query(LedgerEntry)
        .options(joinedload(LedgerEntry.transaction))
        .filter_by(wallet_id=wallet.id)
        .order_by(LedgerEntry.created_at.desc())
        .all()
    )

    return {
        "username": current_user.username,
        "wallet_id": wallet.id,
        "entries": [
            {
                "ledger_entry_id": entry.id,
                "transaction_id": entry.transaction_id,
                "trx_code": entry.transaction.trx_code,
                "entry_type": entry.entry_type,
                "amount_bdt": str(entry.amount_bdt),
                "balance_after": str(entry.balance_after),
                "created_at": (
                    entry.created_at.isoformat() if entry.created_at else None
                ),
            }
            for entry in ledger_entries
        ],
    }


@router.get("/ledger/reconciliation")
def reconcile_ledger(db: Session = Depends(get_db)):
    """
    Double-Entry Ledger Integrity Audit.
    Mathematically verifies that across all transactions in history:
    1. Total Debits == Total Credits
    2. Every transaction has exactly 2 ledger entries (1 DEBIT, 1 CREDIT)
    """
    from decimal import Decimal
    from sqlalchemy import func
    from app.models.transaction import LedgerEntry, Transaction

    debit_total = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount_bdt), Decimal("0.00")))
        .filter_by(entry_type="DEBIT")
        .scalar()
    )
    credit_total = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount_bdt), Decimal("0.00")))
        .filter_by(entry_type="CREDIT")
        .scalar()
    )
    txn_count = db.query(func.count(Transaction.id)).scalar()
    entry_count = db.query(func.count(LedgerEntry.id)).scalar()

    diff = debit_total - credit_total
    is_balanced = (diff == Decimal("0.00")) and (entry_count == txn_count * 2)

    return {
        "is_balanced": is_balanced,
        "total_debits_bdt": str(debit_total),
        "total_credits_bdt": str(credit_total),
        "difference_bdt": str(diff),
        "total_transactions": txn_count,
        "total_ledger_entries": entry_count,
        "accounting_rule": "SUM(DEBITS) == SUM(CREDITS) (Double-Entry Invariant)",
        "status": "HEALTHY — 100% RECONCILED" if is_balanced else "CORRUPTED — DISCREPANCY DETECTED",
    }

