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
    def amount_must_be_positive_integer(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Amount must be a positive integer.")
        if value % 1 != 0 or value.as_tuple().exponent < 0:
            raise ValueError("Amount must be a full integer (decimals and floating points are not allowed).")
        return value


class TransferResponse(BaseModel):
    transaction_id: int
    trx_code: str
    sender: str
    recipient: str
    amount_bdt: str
    note: str | None
    status: str
