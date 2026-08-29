"""
SQLAlchemy model: escrow payments.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EscrowPayment(Base):
    """
    Holds funds between a buyer and seller to act as a trust layer for f-commerce.
    Funds are held in a central ESCROW_HOLD wallet until released or cancelled.
    """
    __tablename__ = "escrow_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    buyer_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    seller_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    # Why NUMERIC: precise financial math, no floats.
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    
    # Status: HELD, RELEASED, REFUNDED
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="HELD")
    
    # Why unique idempotency_key: Prevents double-creation of the same escrow hold.
    idempotency_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
