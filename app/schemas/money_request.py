"""
Pydantic schemas for money request endpoints.
"""
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, field_validator, field_serializer


class MoneyRequestCreate(BaseModel):
    payer_username: str
    amount_bdt: Decimal
    note: str | None = None

    @field_validator("amount_bdt", mode="before")
    @classmethod
    def amount_must_be_valid_integer(cls, value: Any) -> Decimal:
        from app.config import settings
        
        try:
            d = Decimal(str(value))
        except Exception:
            raise ValueError("Invalid decimal format.")

        # WHY: a negative request amount would invert the transfer direction
        if d <= 0 or d > settings.MAX_REQUEST_AMOUNT:
            raise ValueError(f"Amount must be > 0 and <= {settings.MAX_REQUEST_AMOUNT}.")
        return d


class MoneyRequestResponse(BaseModel):
    request_id: int
    requester: str
    payer: str
    amount_bdt: str
    note: str | None
    status: str

    @field_validator("amount_bdt", mode="before")
    @classmethod
    def format_amount(cls, value: Any) -> str:
        if isinstance(value, Decimal):
            return f"{value:.2f}"
        return str(value)


class MoneyRequestActionResponse(BaseModel):
    request_id: int
    status: str
    message: str
