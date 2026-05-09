"""Pipeline run endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_db
from ..worker import start_run
from ...db.models import Run, RunStatus

router = APIRouter(prefix="/runs", tags=["runs"])


class RunCreate(BaseModel):
    vod_id: str
    channel: str = ""
    provider: str | None = None


@router.post("", status_code=201)
def create_run(
    body: RunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    run = Run(vod_id=body.vod_id, channel=body.channel, status=RunStatus.pending)
    db.add(run)
    db.commit()
    db.refresh(run)
    background_tasks.add_task(start_run, run.id, body.vod_id, body.channel, body.provider)
    return run.to_dict()


@router.get("")
def list_runs(db: Session = Depends(get_db)) -> list[dict]:
    runs = db.query(Run).order_by(Run.created_at.desc()).all()
    return [r.to_dict() for r in runs]


@router.get("/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)) -> dict:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run.to_dict()
