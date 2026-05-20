"""Pipeline run endpoints."""

from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..deps import get_db, verify_api_key
from ..worker import start_run
from ...db.models import Run, RunStatus

router = APIRouter(prefix="/runs", tags=["runs"])

_VOD_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class RunCreate(BaseModel):
    vod_id: str
    channel: str = ""
    provider: Literal["anthropic", "openai", "ollama"] | None = None
    prompt_version: Literal["v1", "v2"] = "v1"

    @field_validator("vod_id")
    @classmethod
    def validate_vod_id(cls, v: str) -> str:
        if not _VOD_ID_RE.match(v):
            raise ValueError("vod_id must be 1–64 alphanumeric characters, underscores, or hyphens")
        return v


@router.post(
    "", status_code=201, summary="Create a pipeline run", dependencies=[Depends(verify_api_key)]
)
def create_run(
    body: RunCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """Start an async pipeline run for the given VOD ID. Returns the new run record.

    Returns 429 if a run is already in progress on this server.
    """
    if request.app.state.active_run_id is not None:
        raise HTTPException(429, "A pipeline run is already in progress")
    run = Run(
        vod_id=body.vod_id,
        channel=body.channel,
        status=RunStatus.pending,
        prompt_version=body.prompt_version,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    request.app.state.active_run_id = run.id
    background_tasks.add_task(
        start_run,
        run.id,
        body.vod_id,
        body.channel,
        body.provider,
        request.app,
        body.prompt_version,
    )
    return run.to_dict()


@router.get("", summary="List all runs")
def list_runs(db: Session = Depends(get_db)) -> list[dict]:
    """Return all pipeline runs ordered by creation time descending."""
    runs = db.query(Run).order_by(Run.created_at.desc()).all()
    return [r.to_dict() for r in runs]


@router.get("/{run_id}", summary="Get a run by ID")
def get_run(run_id: int, db: Session = Depends(get_db)) -> dict:
    """Return a single run record. 404 if not found."""
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run.to_dict()
