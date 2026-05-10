"""FastAPI shared dependencies."""

from __future__ import annotations

from functools import lru_cache
from typing import Generator

from fastapi import HTTPException, Request
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from ..config.loaders import Secrets, load_secrets
from ..db.session import get_session

# Registered for OpenAPI /docs security scheme display only.
api_key_header_scheme = APIKeyHeader(name="X-Api-Key", auto_error=False)


@lru_cache(maxsize=1)
def _secrets() -> Secrets:
    return load_secrets()


def get_db() -> Generator[Session, None, None]:
    db = get_session()
    try:
        yield db
    finally:
        db.close()


def verify_api_key(request: Request) -> None:
    """Raise 401 when api_key is configured and the header value doesn't match."""
    expected = _secrets().clipsmith_api_key
    if expected and request.headers.get("x-api-key") != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
