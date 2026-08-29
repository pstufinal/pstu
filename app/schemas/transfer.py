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
    def amount_must_be_positive_and_valid_decimal(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Amount must be positive.")
        if value.as_tuple().exponent < -2:
            raise ValueError("Amount cannot have more than 2 decimal places.")
        return value


class TransferResponse(BaseModel):
    transaction_id: int
    sender: str
    recipient: str
    amount_bdt: str
    note: str | None
    status: str
