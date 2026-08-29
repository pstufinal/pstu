"""
Pydantic schemas for authentication endpoints.
"""
from pydantic import BaseModel, field_validator


class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_must_be_valid(cls, value: str) -> str:
        if len(value) < 3 or len(value) > 50:
            raise ValueError("Username must be 3–50 characters.")
        if not all(c.isalnum() or c == "_" for c in value):
            raise ValueError("Username must be alphanumeric (underscores allowed).")
        return value.lower()

    @field_validator("password")
    @classmethod
    def password_must_be_long_enough(cls, value: str) -> str:
        if len(value) < 6:
            raise ValueError("Password must be at least 6 characters.")
        return value


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterResponse(BaseModel):
    user_id: int
    username: str
    wallet_balance_bdt: str
    message: str
