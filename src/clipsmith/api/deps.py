"""FastAPI shared dependencies."""

from __future__ import annotations

import hmac
import os
from typing import Generator

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from ..db.session import get_session


def get_db() -> Generator[Session, None, None]:
    db = get_session()
    try:
        yield db
    finally:
        db.close()


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Require X-Api-Key header when CLIPSMITH_API_KEY env var is set."""
    expected = os.getenv("CLIPSMITH_API_KEY")
    if expected and not hmac.compare_digest(x_api_key or "", expected):
        raise HTTPException(401, "Invalid or missing API key")
