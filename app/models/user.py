"""
SQLAlchemy model: application user.
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Why index + unique: username lookups happen on every login and every transfer;
    # the unique constraint also prevents duplicate registrations at the DB level.
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Why uselist=False: one user has exactly one wallet, enforced by DB unique constraint on wallet.user_id.
    wallet: Mapped["Wallet"] = relationship(
        "Wallet", back_populates="owner", uselist=False
    )
