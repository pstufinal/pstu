"""
Wallet service: creation and balance queries.
"""
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.models.wallet import Wallet


def create_wallet_for_user(db: Session, user_id: int) -> Wallet:
    """
    Why auto-create with a fixed initial balance: every registered user can
    immediately participate without a separate funding / KYC step.
    The 100 000 BDT is fake money for this hackathon demo.
    """
    wallet = Wallet(
        user_id=user_id,
        balance=settings.INITIAL_BALANCE_BDT,
    )
    db.add(wallet)
    # Why flush not commit: the caller (register endpoint) controls the transaction
    # boundary so user + wallet creation is atomic.
    db.flush()
    return wallet


def get_wallet_balance(db: Session, user_id: int) -> Wallet:
    """
    Why query by user_id not wallet_id: the API consumer knows their user identity,
    not their internal wallet primary key.
    """
    wallet = db.query(Wallet).filter_by(user_id=user_id).first()
    if wallet is None:
        raise ValueError(f"No wallet found for user_id={user_id}")
    return wallet
