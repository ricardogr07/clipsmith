"""SQLAlchemy engine initialisation and session factory."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None  # type: ignore[type-arg]


def _default_url() -> str:
    return f"sqlite:///{Path('work/clipsmith.db').resolve()}"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", _default_url())


def init_db(db_path: Path | str | None = None) -> None:
    """Create engine, run DDL, store session factory.

    DATABASE_URL env var takes precedence over db_path for flexibility in
    production (PostgreSQL) while keeping backward-compat with existing callers.
    """
    global _engine, _SessionLocal

    url = os.getenv("DATABASE_URL")
    if url is None and db_path is not None:
        url = f"sqlite:///{db_path}"
    if url is None:
        url = _default_url()

    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, connect_args=connect_args)
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(_engine)


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("DB not initialised — call init_db() before using get_session()")
    return _SessionLocal()
