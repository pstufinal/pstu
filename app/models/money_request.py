"""
SQLAlchemy model: money request (one user asks another for payment).
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MoneyRequest(Base):
    """
    A request from one user (requester) asking another user (payer) for money.
    Status lifecycle: pending → approved | rejected.
    """
    __tablename__ = "money_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requester_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    payer_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    # Why NUMERIC: same as everywhere else — exact decimal, no float.
    amount_bdt: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Why VARCHAR not ENUM for status: simpler migrations, no ALTER TYPE needed.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
