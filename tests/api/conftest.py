"""Shared fixtures for the FastAPI API test suite."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from clipsmith.api.app import app
from clipsmith.api.deps import get_db
from clipsmith.db.models import Base


@pytest.fixture
def _db_context():
    """In-memory SQLite engine + session factory, shared via StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture
def client(_db_context):
    def override_db():
        db: Session = _db_context()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with (
        patch("clipsmith.api.app.init_db"),
        patch("clipsmith.api.routes.runs.start_run"),
    ):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


@pytest.fixture
def db_session(_db_context):
    """Direct DB session sharing the same in-memory engine as `client`."""
    db: Session = _db_context()
    yield db
    db.close()
