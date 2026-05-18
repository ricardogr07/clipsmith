"""Clip management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_db, verify_api_key
from ...db.models import Clip, Run

router = APIRouter(tags=["clips"])


class ClipPatch(BaseModel):
    approved: bool


@router.get("/runs/{run_id}/clips", summary="List clips for a run")
def list_clips(run_id: int, db: Session = Depends(get_db)) -> list[dict]:
    """Return all clips produced by the given run. 404 if run not found."""
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return [c.to_dict() for c in run.clips]


@router.patch(
    "/clips/{clip_id}", summary="Approve or reject a clip", dependencies=[Depends(verify_api_key)]
)
def patch_clip(clip_id: int, body: ClipPatch, db: Session = Depends(get_db)) -> dict:
    """Set approved=true/false on a clip. 404 if clip not found."""
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    clip.approved = body.approved
    db.commit()
    db.refresh(clip)
    return clip.to_dict()
