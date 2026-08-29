"""
Database engine and session factory.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


# Why pool_pre_ping: detects stale connections before handing them to a request,
# preventing "connection already closed" errors after PostgreSQL restarts.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Why autoflush=False: prevents SQLAlchemy from auto-flushing dirty objects before
# every query, giving us explicit control over when writes hit the DB.
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Why DeclarativeBase over legacy declarative_base(): SQLAlchemy 2.x recommended pattern,
    provides better type-checking support and mapped_column integration."""
    pass


def get_db():
    """
    Why yield + finally: guarantees the session is closed even if the request
    handler raises, preventing connection pool exhaustion under load.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
