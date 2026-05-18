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


@router.get("/runs/{run_id}/clips/file/{filename}", summary="Download a clip file")
def serve_clip(run_id: int, filename: str, db: Session = Depends(get_db)) -> FileResponse:
    """Serve the MP4 clip file associated with the given run and filename."""
    if "/" in filename or "\\" in filename or ".." in filename or not filename.endswith(".mp4"):
        raise HTTPException(400, "Invalid filename")

    clip = db.query(Clip).filter(Clip.run_id == run_id, Clip.filename == filename).first()
    if not clip:
        raise HTTPException(404, "Clip not found")

    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    cfg = load_config(Path("config.yaml"))
    out_root = cfg.out_dir.expanduser().resolve()
    mp4_path = (out_root / run.vod_id / filename).resolve()
    if not mp4_path.is_relative_to(out_root):
        raise HTTPException(400, "Invalid path")
    if not mp4_path.exists():
        raise HTTPException(404, "Clip file not found")

    return FileResponse(str(mp4_path), media_type="video/mp4")
