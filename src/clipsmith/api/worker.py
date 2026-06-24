"""Background worker: runs process_vod in a thread and emits DB events."""

from __future__ import annotations

import json
import logging
import re
import shutil
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.orm import Session

from ..db.models import Clip, PipelineEvent, Run, RunStatus
from ..db.session import get_session
from ..models.twitch import Video
from ..pipeline import process_vod
from ..settings import AppConfig, load_config, load_secrets
from ..telemetry import CLIPS_APPROVED, RUNS_TOTAL, STAGE_DURATION, stage_duration, tracer  # noqa: F401

log = logging.getLogger(__name__)


def start_run(
    run_id: int,
    vod_id: str,
    channel: str,
    provider: str | None,
    app: Any = None,
    prompt_version: str = "v1",
    start_s: float = 0.0,
    end_s: float = 0.0,
    cloud: bool = False,
) -> None:
    """Entry point for BackgroundTasks. Opens its own DB session for thread safety."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id=run_id, vod_id=vod_id)
    db = get_session()
    try:
        if cloud:
            _run_cloud_pipeline(
                db, run_id, vod_id, channel, provider,
                prompt_version=prompt_version, start_s=start_s, end_s=end_s,
            )
        else:
            _run_pipeline(
                db, run_id, vod_id, channel, provider,
                prompt_version=prompt_version, start_s=start_s, end_s=end_s,
            )
        RUNS_TOTAL.labels(status="done").inc()
    except Exception as exc:
        log.exception("pipeline failed for run %d vod=%s", run_id, vod_id)
        RUNS_TOTAL.labels(status="failed").inc()
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
    start_s: float = 0.0,
    end_s: float = 0.0,
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

    _stage_start: dict[str, tuple] = {}  # stage → (span, t0)

    def on_stage(stage: str, pct: float) -> None:
        for prev, (span, t0) in list(_stage_start.items()):
            elapsed = time.monotonic() - t0
            stage_duration.record(elapsed, {"stage": prev, "vod_id": vod_id})
            STAGE_DURATION.labels(stage=prev).observe(elapsed)
            span.end()
            del _stage_start[prev]

        span = tracer.start_span(
            f"pipeline.{stage}",
            attributes={"run_id": str(run_id), "vod_id": vod_id, "stage": stage},
        )
        _stage_start[stage] = (span, time.monotonic())
        _emit(db, run_id, stage, pct)

    _emit(db, run_id, "starting", 0.0, "pipeline starting")

    with tracer.start_as_current_span(
        "pipeline.run", attributes={"run_id": str(run_id), "vod_id": vod_id}
    ):
        process_vod(
            video, cfg, secrets,
            on_stage=on_stage, prompt_version=prompt_version,
            start_s=start_s, end_s=end_s,
        )

    for stage, (span, t0) in list(_stage_start.items()):
        elapsed = time.monotonic() - t0
        stage_duration.record(elapsed, {"stage": stage, "vod_id": vod_id})
        STAGE_DURATION.labels(stage=stage).observe(elapsed)
        span.end()

    _harvest_clips(db, run_id, vod_id, cfg)
    _emit(db, run_id, "done", 100.0, "pipeline complete", status=RunStatus.done)


def _run_cloud_pipeline(
    db: Session,
    run_id: int,
    vod_id: str,
    channel: str,
    provider: str | None,
    *,
    prompt_version: str = "v1",
    start_s: float = 0.0,
    end_s: float = 0.0,
) -> None:
    """Offload the pipeline to an ephemeral ACI container group."""
    from ..cloud.provisioner import provision_run_resources, teardown_run_resources
    from ..cloud.azure_runner import (
        upload_config,
        create_container_group,
        poll_until_done,
        download_output,
    )

    cfg = load_config(Path("config.yaml"))
    secrets = load_secrets()

    if not cfg.cloud.docker_image:
        raise RuntimeError("config.cloud.docker_image must be set to use cloud runs")

    run_ctx = None
    try:
        _emit(db, run_id, "provisioning", 5.0, "creating ephemeral Azure resources")
        run_ctx = provision_run_resources(vod_id, cfg, secrets)
        log.info("provisioned run context: rg=%s sa=%s", run_ctx.resource_group, run_ctx.storage_account)

        _emit(db, run_id, "uploading", 10.0, "uploading config to file share")
        upload_config(Path("config.yaml"), secrets, run_ctx)

        _emit(db, run_id, "starting_aci", 15.0, "creating ACI container group")
        group_name = create_container_group(vod_id, cfg, secrets, run_ctx=run_ctx)
        log.info("ACI container group created: %s", group_name)

        _emit(db, run_id, "processing", 20.0, "ACI pipeline running — polling every 30s")
        state = poll_until_done(group_name, cfg, secrets, run_ctx=run_ctx, verbose=True)

        if state != "Succeeded":
            raise RuntimeError(f"ACI job finished with state '{state}' — check Azure portal logs")

        _emit(db, run_id, "downloading", 90.0, "downloading clips from file share")
        out_dir = cfg.work_dir.expanduser().parent / "out" / vod_id
        out_dir.mkdir(parents=True, exist_ok=True)
        clip_paths = download_output(vod_id, secrets, run_ctx)
        for p in clip_paths:
            shutil.copy2(p, out_dir / p.name)
        log.info("downloaded %d clips to %s", len(clip_paths), out_dir)

        _harvest_clips(db, run_id, vod_id, cfg)
        _emit(db, run_id, "done", 100.0, "pipeline complete", status=RunStatus.done)

    finally:
        if run_ctx is not None:
            try:
                teardown_run_resources(run_ctx, secrets)
                log.info("ephemeral Azure resources deleted")
            except Exception:
                log.exception("teardown failed for run %d — Azure resources may need manual cleanup", run_id)


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
