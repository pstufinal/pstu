"""
Money validation utilities.
Why this module exists: centralises all monetary validation so no service
can accidentally skip a check. Defense-in-depth on top of Pydantic schemas.
"""
from decimal import Decimal

from fastapi import HTTPException


# Why Decimal constants: using float literals like 0.0 would silently convert
# Decimal comparisons to float, re-introducing the exact bug we're avoiding.
ZERO = Decimal("0.00")
MAX_TRANSFER_BDT = Decimal("10000000.00")  # 10 million BDT sanity ceiling


def validate_amount(amount_bdt: Decimal) -> Decimal:
    """
    Why validate here AND in Pydantic: Pydantic guards the API boundary,
    this guards against bugs in our own service code that constructs amounts.
    """
    if amount_bdt <= ZERO:
        raise HTTPException(
            status_code=400,
            detail="Amount must be positive.",
        )
    if amount_bdt > MAX_TRANSFER_BDT:
        raise HTTPException(
            status_code=400,
            detail="Amount exceeds maximum transfer limit.",
        )
    # Why quantize check: prevents transfers of e.g. 10.999 BDT which would
    # silently round in the DB but not in Python, causing ledger drift.
    rounded = amount_bdt.quantize(Decimal("0.01"))
    if amount_bdt != rounded:
        raise HTTPException(
            status_code=400,
            detail="Amount must have at most 2 decimal places.",
        )
    return amount_bdt
