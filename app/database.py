"""
Database engine and session factory.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


# Why connection pooling: PgBouncer goes in front at ~5K concurrent users.
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,
)

# Replica engine for read/write splitting
if settings.READ_DATABASE_URL:
    replica_engine = create_engine(
        settings.READ_DATABASE_URL,
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_timeout=30,
    )
else:
    replica_engine = engine

# Why autoflush=False: prevents SQLAlchemy from auto-flushing dirty objects before
# every query, giving us explicit control over when writes hit the DB.
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
ReadSessionLocal = sessionmaker(bind=replica_engine, autocommit=False, autoflush=False)


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


def get_read_db():
    """
    Why separate read DB: routes pure GET requests to read replicas without touching
    the primary database, enabling massive scale-out for read-heavy operations.
    """
    db = ReadSessionLocal()
    try:
        yield db
    finally:
        db.close()
