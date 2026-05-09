"""Static file serving: MP4 clips scoped to a specific run."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ...db.models import Clip, Run
from ..deps import get_db
from ...settings import load_config

router = APIRouter(tags=["files"])


@router.get("/runs/{run_id}/clips/file/{filename}")
def serve_clip(run_id: int, filename: str, db: Session = Depends(get_db)) -> FileResponse:
    if "/" in filename or "\\" in filename or ".." in filename or not filename.endswith(".mp4"):
        raise HTTPException(400, "Invalid filename")

    clip = db.query(Clip).filter(Clip.run_id == run_id, Clip.filename == filename).first()
    if not clip:
        raise HTTPException(404, f"Clip not found: {filename}")

    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    cfg = load_config(Path("config.yaml"))
    mp4_path = cfg.out_dir.expanduser() / run.vod_id / filename
    if not mp4_path.exists():
        raise HTTPException(404, f"Clip file missing on disk: {filename}")

    return FileResponse(str(mp4_path), media_type="video/mp4")
