"""FastAPI shared dependencies."""

from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from ..db.session import get_session


def get_db() -> Generator[Session, None, None]:
    db = get_session()
    try:
        yield db
    finally:
        db.close()
