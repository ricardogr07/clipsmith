"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .routes import clips, files, health, publish, runs, stream
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


app = FastAPI(
    title="clipsmith API",
    description="REST API for the clipsmith AI clip pipeline.",
    version="1.0.0",
    docs_url="/docs",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router)
app.include_router(clips.router)
app.include_router(stream.router)
app.include_router(files.router)
app.include_router(health.router)
app.include_router(publish.router)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse("/docs")
