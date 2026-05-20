"""SQLAlchemy engine initialisation and session factory."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

log = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None  # type: ignore[type-arg]

# Inline schema migrations for columns added after the initial DB was created.
# Remove each entry once Sprint 9 (Alembic) is in place and the migration is
# handled there instead.
_COLUMN_MIGRATIONS = [
    ("runs", "prompt_version", "VARCHAR(32) NOT NULL DEFAULT 'v1'"),
    ("clips", "signal_breakdown", "JSON"),
]


def _apply_column_migrations(engine: Engine) -> None:
    """Add columns to existing tables that pre-date the current model."""
    with engine.begin() as conn:
        for table, column, definition in _COLUMN_MIGRATIONS:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
                log.info("schema migration: added %s.%s", table, column)
            except Exception:
                pass  # column already exists — SQLite raises OperationalError


def init_db(db_path: Path | str = "clipsmith.db") -> None:
    """Create engine, run DDL (create tables if missing), store session factory."""
    global _engine, _SessionLocal
    _engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(_engine)  # no-op for tables that already exist
    _apply_column_migrations(_engine)  # add new columns to pre-existing tables


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("DB not initialised — call init_db() before using get_session()")
    return _SessionLocal()
