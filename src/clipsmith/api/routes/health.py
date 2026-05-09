"""Health and metrics endpoints."""

from __future__ import annotations

from importlib.metadata import version, PackageNotFoundError

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db
from ...db.models import Run, RunStatus

router = APIRouter(tags=["system"])

try:
    _VERSION = version("clipsmith-ai")
except PackageNotFoundError:
    _VERSION = "dev"


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {"status": "ok", "db": db_status, "version": _VERSION}


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> dict:
    counts = {s.value: db.query(Run).filter(Run.status == s).count() for s in RunStatus}
    return {"runs_by_status": counts}
