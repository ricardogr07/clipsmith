"""Shared fixtures for API integration tests.

Replaces the production lifespan with a no-op so tests never need config.yaml,
primes the global DB with an in-memory SQLite instance, and overrides get_db
to give each test a clean session.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from clipsmith.api.app import app
from clipsmith.api.deps import get_db
from clipsmith.db import session as _db_session_module
from clipsmith.db.models import Base

VALID_KEY = "test-secret"

# ── In-memory SQLite with StaticPool: one connection for all sessions ─────────
# StaticPool ensures every engine.connect() call reuses the same underlying
# SQLite connection, so all sessions see the same in-memory database.

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
Base.metadata.create_all(_engine)

# Prime the global session module so get_session() resolves without lifespan
_db_session_module._engine = _engine
_db_session_module._SessionLocal = _TestSession


# ── Replace lifespan so TestClient never touches config.yaml ─────────────────


@asynccontextmanager
async def _noop_lifespan(application: object) -> AsyncGenerator[None, None]:  # type: ignore[type-arg]
    app.state.active_run_id = None
    yield


app.router.lifespan_context = _noop_lifespan


# ── Per-test fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLIPSMITH_API_KEY", VALID_KEY)


@pytest.fixture(autouse=True)
def _reset_active_run() -> Generator[None, None, None]:
    app.state.active_run_id = None
    yield
    app.state.active_run_id = None


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = _TestSession()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    def _override() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()
