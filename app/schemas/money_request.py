"""
Pydantic schemas for money request endpoints.
"""
from decimal import Decimal

from pydantic import BaseModel, field_validator


class MoneyRequestCreate(BaseModel):
    payer_username: str
    amount_bdt: Decimal
    note: str | None = None

    @field_validator("amount_bdt")
    @classmethod
    def amount_must_be_valid_integer(cls, value: Decimal) -> Decimal:
        from app.config import settings
        # WHY: a negative request amount would invert the transfer direction
        if value <= 0 or value > settings.MAX_REQUEST_AMOUNT:
            raise ValueError(f"Amount must be > 0 and <= {settings.MAX_REQUEST_AMOUNT}.")
        if value % 1 != 0 or value.as_tuple().exponent < 0:
            raise ValueError("Amount must be a full integer (decimals and floating points are not allowed).")
        return value


class MoneyRequestResponse(BaseModel):
    request_id: int
    requester: str
    payer: str
    amount_bdt: str
    note: str | None
    status: str


class MoneyRequestActionResponse(BaseModel):
    request_id: int
    status: str
    message: str
