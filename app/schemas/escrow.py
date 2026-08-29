"""
Pydantic schemas for Escrow operations.
"""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class EscrowCreate(BaseModel):
    seller_username: str = Field(..., min_length=1, max_length=50)
    amount_bdt: Decimal = Field(..., gt=0, decimal_places=2)
    note: str | None = Field(None, max_length=255)


class EscrowResponse(BaseModel):
    id: int
    buyer_user_id: int
    seller_user_id: int
    amount: Decimal
    status: str
    idempotency_key: str
    note: str | None
    created_at: datetime
    decided_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
