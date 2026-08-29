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
    def amount_must_be_positive_and_valid_decimal(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Amount must be positive.")
        if value.as_tuple().exponent < -2:
            raise ValueError("Amount cannot have more than 2 decimal places.")
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
