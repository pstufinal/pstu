"""
Pydantic schemas for money transfer endpoints.
"""
from decimal import Decimal

from pydantic import BaseModel, field_validator


class TransferRequest(BaseModel):
    recipient_username: str
    # Why Decimal in the schema: catches float-as-string at the API boundary
    # before it can contaminate business logic with imprecise arithmetic.
    amount_bdt: Decimal
    note: str | None = None

    @field_validator("amount_bdt")
    @classmethod
    def amount_must_be_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Amount must be positive.")
        return value


class TransferResponse(BaseModel):
    transaction_id: int
    sender: str
    recipient: str
    amount_bdt: str
    note: str | None
    status: str
