"""Health, metrics, and stats endpoints."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..deps import get_db
from ...db.models import Run, RunStatus

router = APIRouter(tags=["system"])

try:
    _VERSION = version("clipsmith-ai")
except PackageNotFoundError:
    _VERSION = "dev"

try:
    from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False


@router.get("/health", summary="Health check")
def health(db: Session = Depends(get_db)) -> dict:
    """Return server and database status. Always 200; check 'db' field for DB health."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {"status": "ok", "db": db_status, "version": _VERSION}


@router.get("/metrics", response_class=Response, summary="Prometheus metrics scrape endpoint")
def prometheus_metrics() -> Response:
    """Return all metrics in Prometheus text format for scraping by Prometheus."""
    if not _PROMETHEUS_AVAILABLE:
        return Response(
            "# prometheus_client not installed; pip install 'clipsmith-ai[observability]'\n",
            media_type="text/plain",
        )
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


@router.get("/stats", summary="Run status counts (JSON)")
def stats(db: Session = Depends(get_db)) -> dict:
    """Return pipeline run counts grouped by status (pending/running/done/failed)."""
    counts = {s.value: db.query(Run).filter(Run.status == s).count() for s in RunStatus}
    return {"runs_by_status": counts}
