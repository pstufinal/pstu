"""
Pydantic schemas for money transfer endpoints.
"""
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, field_validator, field_serializer


class TransferRequest(BaseModel):
    recipient_username: str
    # Why Decimal in the schema: catches float-as-string at the API boundary
    # before it can contaminate business logic with imprecise arithmetic.
    amount_bdt: Decimal
    note: str | None = None

    @field_validator("amount_bdt", mode="before")
    @classmethod
    def amount_must_be_positive_integer(cls, value: Any) -> Decimal:
        # Pydantic will cast string/int to Decimal automatically, but we enforce rules.
        try:
            d = Decimal(str(value))
        except Exception:
            raise ValueError("Invalid decimal format.")
        
        if d <= 0:
            raise ValueError("Amount must be a positive number.")
        return d


class TransferResponse(BaseModel):
    transaction_id: int
    trx_code: str
    sender: str
    recipient: str
    amount_bdt: str
    note: str | None
    status: str

    @field_validator("amount_bdt", mode="before")
    @classmethod
    def format_amount(cls, value: Any) -> str:
        if isinstance(value, Decimal):
            return f"{value:.2f}"
        return str(value)
