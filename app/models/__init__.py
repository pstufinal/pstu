"""
Import all models so SQLAlchemy registers them with Base.metadata.
This must be imported before Base.metadata.create_all() is called.
"""
from app.models.user import User
from app.models.wallet import Wallet
from app.models.transaction import Transaction, LedgerEntry, IdempotencyRecord
from app.models.money_request import MoneyRequest

__all__ = [
    "User",
    "Wallet",
    "Transaction",
    "LedgerEntry",
    "IdempotencyRecord",
    "MoneyRequest",
]
