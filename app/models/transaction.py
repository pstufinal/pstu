"""
SQLAlchemy models: Transaction, LedgerEntry (double-entry), IdempotencyRecord.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Transaction(Base):
    """Represents a completed money transfer between two wallets."""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_wallet_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wallets.id"), nullable=False, index=True
    )
    recipient_wallet_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wallets.id"), nullable=False, index=True
    )
    # Why NUMERIC: same reason as wallet balance — exact arithmetic, no float drift.
    amount_bdt: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    # Why type column: distinguishes regular transfers from escrow hold/release/refund
    # without needing complex joins or new tables.
    type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="TRANSFER")
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Why unique constraint on idempotency_key: DB-level guarantee against double-charge,
    # even if the application-level check races with a concurrent request.
    idempotency_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(
        "LedgerEntry", back_populates="transaction"
    )


class LedgerEntry(Base):
    """
    Double-entry ledger: every Transaction produces exactly two LedgerEntry rows
    (one DEBIT, one CREDIT). Globally, SUM(debits) must always equal SUM(credits).
    """
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("transactions.id"), nullable=False, index=True
    )
    wallet_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wallets.id"), nullable=False, index=True
    )
    # Why VARCHAR not ENUM: easier to add new entry types later without an ALTER TYPE migration.
    entry_type: Mapped[str] = mapped_column(String(10), nullable=False)  # DEBIT or CREDIT
    amount_bdt: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    # Why balance_after: enables point-in-time auditing without replaying the entire ledger.
    balance_after: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    transaction: Mapped["Transaction"] = relationship(
        "Transaction", back_populates="ledger_entries"
    )


class IdempotencyRecord(Base):
    """
    Caches the response of completed transfers keyed by idempotency_key,
    so retried requests return the original result without re-executing the transfer.
    """
    __tablename__ = "idempotency_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Why unique: the DB is the final arbiter — even if two threads pass the app-level
    # check simultaneously, only one INSERT succeeds; the other gets IntegrityError.
    idempotency_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    response_payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
