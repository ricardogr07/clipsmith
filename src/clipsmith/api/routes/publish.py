"""Publishing endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db, verify_api_key
from ...db.models import Clip
from ...publish.youtube import YouTubePublisher
from ...settings import load_config

router = APIRouter(tags=["publish"])


@router.post(
    "/clips/{clip_id}/publish",
    summary="Publish an approved clip to YouTube Shorts",
    dependencies=[Depends(verify_api_key)],
)
def publish_clip(clip_id: int, db: Session = Depends(get_db)) -> dict:
    """Upload the clip file to YouTube Shorts and persist the watch URL.

    Returns 422 if the clip is not approved.
    Returns 200 with the existing URL if already published (idempotent).
    """
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    if not clip.approved:
        raise HTTPException(422, "Clip must be approved before publishing")
    if clip.published_url:
        return clip.to_dict()

    cfg = load_config(Path("config.yaml"))
    out_root = cfg.out_dir.expanduser().resolve()
    video_path = (out_root / clip.filename).resolve()
    if not video_path.is_relative_to(out_root):
        raise HTTPException(400, "Invalid clip path")
    if not video_path.exists():
        raise HTTPException(404, "Clip file not found")

    publisher = YouTubePublisher(
        credentials_file=cfg.publish.youtube_credentials,
        token_file=cfg.publish.youtube_token,
    )
    url = publisher.upload(
        video_path,
        title=clip.title or clip.filename,
        privacy=cfg.publish.youtube_privacy,
        category_id=cfg.publish.youtube_category,
    )
    clip.published_url = url
    db.commit()
    db.refresh(clip)
    return clip.to_dict()
