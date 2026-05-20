"""FastAPI application factory."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .routes import analytics, clips, files, health, publish, runs, stream
from ..db.session import init_db
from ..settings import load_config


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    cfg = load_config(Path("config.yaml"))
    db_path = cfg.work_dir.expanduser() / "clipsmith.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db(db_path)
    app.state.active_run_id = None  # int | None; cleared by worker on completion
    yield


_TAGS: list[dict] = [
    {
        "name": "runs",
        "description": "Pipeline run lifecycle — create, list, and inspect VOD processing runs.",
    },
    {
        "name": "clips",
        "description": "Clip review — list clips produced by a run and approve/reject them.",
    },
    {
        "name": "analytics",
        "description": (
            "Signal and prompt analytics — compare which signals drive approvals "
            "and which prompt version performs best."
        ),
    },
    {
        "name": "stream",
        "description": "Server-Sent Events stream of live pipeline progress for a run.",
    },
    {
        "name": "publish",
        "description": "Publish approved clips to YouTube Shorts.",
    },
    {
        "name": "files",
        "description": "Download the raw MP4 file for a clip.",
    },
    {
        "name": "system",
        "description": "Health check and run-count metrics.",
    },
]

app = FastAPI(
    title="clipsmith API",
    description=(
        "REST API for the **clipsmith** AI clip pipeline.\n\n"
        "clipsmith converts Twitch VODs into vertical 9:16 short-form clips using a "
        "6-stage pipeline (download → transcribe → chat → candidates → LLM selection → render). "
        "This API drives the Next.js dashboard and exposes analytics for the ML feedback loop.\n\n"
        "## Authentication\n"
        "Mutating endpoints (`POST /runs`, `PATCH /clips`, `POST /clips/{id}/publish`, "
        "`POST /analytics/runs/{id}/calibrate`) require an `X-Api-Key` header when "
        "`CLIPSMITH_API_KEY` is set in the server environment. Read endpoints are open.\n\n"
        "## Quick start\n"
        "```bash\n"
        "# Start a pipeline run\n"
        "curl -X POST http://localhost:8000/runs \\\n"
        '  -H "X-Api-Key: $CLIPSMITH_API_KEY" \\\n'
        '  -H "Content-Type: application/json" \\\n'
        '  -d \'{"vod_id":"2341234567","channel":"xqc","prompt_version":"v1"}\'\n'
        "```"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=_TAGS,
    contact={"name": "Ricardo García", "url": "https://github.com/ricardogr07/clipsmith"},
    license_info={"name": "MIT"},
    lifespan=_lifespan,
)

_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Api-Key"],
)

app.include_router(runs.router)
app.include_router(clips.router)
app.include_router(stream.router)
app.include_router(files.router)
app.include_router(health.router)
app.include_router(publish.router)
app.include_router(analytics.router)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse("/docs")
