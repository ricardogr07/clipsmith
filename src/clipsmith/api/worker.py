"""Background worker: runs process_vod in a thread and emits DB events."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

import structlog
from pathlib import Path

from sqlalchemy.orm import Session

from ..db.models import Clip, PipelineEvent, Run, RunStatus
from ..db.session import get_session
from ..models.twitch import Video
from ..pipeline import process_vod
from ..settings import AppConfig, load_config, load_secrets

log = logging.getLogger(__name__)


def start_run(
    run_id: int,
    vod_id: str,
    channel: str,
    provider: str | None,
    app: Any = None,
    prompt_version: str = "v1",
) -> None:
    """Entry point for BackgroundTasks. Opens its own DB session for thread safety."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id=run_id, vod_id=vod_id)
    db = get_session()
    try:
        _run_pipeline(db, run_id, vod_id, channel, provider, prompt_version=prompt_version)
    except Exception as exc:
        log.exception("pipeline failed for run %d vod=%s", run_id, vod_id)
        try:
            run = db.get(Run, run_id)
            if run:
                run.status = RunStatus.failed
                run.error = str(exc)
                run.updated_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            log.exception("could not persist failure state for run %d", run_id)
    finally:
        db.close()
        if app is not None:
            app.state.active_run_id = None


def _emit(
    db: Session,
    run_id: int,
    stage: str,
    pct: float,
    message: str = "",
    *,
    status: RunStatus = RunStatus.running,
) -> None:
    run = db.get(Run, run_id)
    if run:
        run.stage = stage
        run.status = status
        run.updated_at = datetime.now(timezone.utc)
    ev = PipelineEvent(run_id=run_id, stage=stage, pct=pct, message=message)
    db.add(ev)
    db.commit()


def _run_pipeline(
    db: Session,
    run_id: int,
    vod_id: str,
    channel: str,
    provider: str | None,
    *,
    prompt_version: str = "v1",
) -> None:
    cfg = load_config(Path("config.yaml"))
    secrets = load_secrets()

    if provider:
        cfg.llm.provider = provider  # type: ignore[assignment]

    video = Video(
        id=vod_id,
        user_id="",
        user_login=channel or "unknown",
        title=vod_id,
        created_at="",
        published_at="",
        url=f"https://www.twitch.tv/videos/{vod_id}",
        duration="",
        type="archive",
    )

    def on_stage(stage: str, pct: float) -> None:
        _emit(db, run_id, stage, pct)

    _emit(db, run_id, "starting", 0.0, "pipeline starting")
    process_vod(video, cfg, secrets, on_stage=on_stage, prompt_version=prompt_version)

    _harvest_clips(db, run_id, vod_id, cfg)
    _emit(db, run_id, "done", 100.0, "pipeline complete", status=RunStatus.done)


def _harvest_clips(db: Session, run_id: int, vod_id: str, cfg: AppConfig) -> None:
    """Read picks.json and create Clip rows in the DB."""
    picks_path = cfg.work_dir.expanduser() / vod_id / "picks.json"
    if not picks_path.exists():
        return

    picks_data = json.loads(picks_path.read_text(encoding="utf-8"))
    for i, item in enumerate(picks_data, 1):
        p = item.get("pick", {})
        cand = item.get("candidate", {})
        title = p.get("title_es", "")
        slug = _title_slug(title)
        filename = f"clip_{i:02d}_{slug}.mp4"
        clip = Clip(
            run_id=run_id,
            filename=filename,
            title=title,
            start_s=p.get("start_offset_s", 0.0),
            end_s=p.get("end_offset_s", 0.0),
            score=cand.get("score", 0.0),
            signal_breakdown=_build_signal_breakdown(cand),
        )
        db.add(clip)
    db.commit()


def _build_signal_breakdown(candidate: dict) -> dict[str, float] | None:
    """Map candidate sources to equal-split score contributions."""
    sources = candidate.get("sources", [])
    total = candidate.get("score", 0.0) or 0.0
    if not sources or total == 0.0:
        return None
    per_source = round(total / len(sources), 2)
    return {src: per_source for src in sources}


def _title_slug(title: str) -> str:
    """Filesystem-safe ASCII slug (mirrors clipper._title_slug)."""
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = "".join(c for c in normalized if not unicodedata.combining(c))
    slug = ascii_only.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "_", slug)
    return slug.strip("_-")[:40] or "clip"
