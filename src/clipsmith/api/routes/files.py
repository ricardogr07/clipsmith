"""Static file serving: MP4 clips from out_dir."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...settings import load_config

router = APIRouter(tags=["files"])


@router.get("/clips/file/{filename}")
def serve_clip(filename: str) -> FileResponse:
    # Reject path traversal and non-MP4 requests before touching the filesystem.
    if "/" in filename or "\\" in filename or ".." in filename or not filename.endswith(".mp4"):
        raise HTTPException(400, "Invalid filename")

    cfg = load_config(Path("config.yaml"))
    out_dir = cfg.out_dir.expanduser()

    for mp4 in out_dir.rglob(filename):
        return FileResponse(str(mp4), media_type="video/mp4")

    raise HTTPException(404, f"Clip not found: {filename}")
