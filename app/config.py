"""
Application configuration loaded from environment variables.
Why pydantic-settings: validates env vars at startup, not at first use,
so misconfiguration crashes early instead of silently at 3 AM in production.
"""
from decimal import Decimal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/moneymove"
    READ_DATABASE_URL: str | None = None
    SECRET_KEY: str = "hackathon-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    INITIAL_BALANCE_BDT: Decimal = Decimal("100000.00")

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
