"""
Public verification endpoint for proof-of-payment.
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, aliased

from app.database import get_read_db
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet

router = APIRouter(prefix="/verify", tags=["verification"])


def mask_username(username: str) -> str:
    """
    Mask username for public display.
    Rule: first 3 chars + "***"
    """
    if len(username) <= 3:
        return username + "***"
    return username[:3] + "***"


@router.get("/{trx_code}")
def verify_transaction(trx_code: str, db: Session = Depends(get_read_db)):
    """
    Public proof-of-payment kills fake payment screenshots in BD f-commerce.
    Returns NO balances, NO history, NO internal IDs. NO auth required.
    """
    # Create aliases for joining the users table twice (sender and recipient)
    SenderWallet = aliased(Wallet)
    RecipientWallet = aliased(Wallet)
    SenderUser = aliased(User)
    RecipientUser = aliased(User)

    result = (
        db.query(Transaction, SenderUser, RecipientUser)
        .join(SenderWallet, Transaction.sender_wallet_id == SenderWallet.id)
        .join(SenderUser, SenderWallet.user_id == SenderUser.id)
        .join(RecipientWallet, Transaction.recipient_wallet_id == RecipientWallet.id)
        .join(RecipientUser, RecipientWallet.user_id == RecipientUser.id)
        .filter(Transaction.trx_code == trx_code)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    transaction, sender, recipient = result

    return {
        "trx_code": transaction.trx_code,
        "type": transaction.type,
        "amount": str(transaction.amount_bdt.quantize(Decimal("0.01"))),
        "status": "completed",
        "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
        "sender_masked": mask_username(sender.username),
        "receiver_masked": mask_username(recipient.username),
    }
