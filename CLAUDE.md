# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Python Backend
```bash
pip install -e ".[dev]"                        # Install with dev extras
pip install -e ".[vision]"                     # Optional: OpenCV for webcam detection
pip install -e ".[server]"                     # FastAPI + uvicorn
pip install -e ".[dev,server,observability]"   # Full stack incl. OTel + Prometheus

clipsmith serve                    # Start FastAPI server
clipsmith process path/to/video.mp4
clipsmith run-vod <vod_id>
clipsmith watch                    # Daemon mode

python -m pytest tests/ -q         # Run all tests (e2e skipped by default)
python -m pytest tests/unit -q     # Unit tests only
python -m pytest tests/ -q --run-e2e  # Include full pipeline e2e tests

ruff check src tests               # Lint
ruff format src tests              # Format
mypy src                           # Type check
```

### Frontend (web/)
```bash
pnpm install
pnpm dev          # Next.js dev server (port 3000)
pnpm build
pnpm cy:open      # Cypress interactive
pnpm storybook    # Storybook (port 6006)
```

> **Windows note:** Cypress Electron binary fails in sandboxed shells — run Cypress commands locally in your own terminal, not via Claude Code tools.

## Architecture

### System Overview

Clipsmith converts Twitch VODs (or local MP4s) into vertical 9:16 short-form clips using a 6-stage pipeline orchestrated by `pipeline.py`. It exposes a FastAPI REST API consumed by a Next.js dashboard.

```
src/clipsmith/         Python backend (package)
web/                   Next.js 16 dashboard
tests/                 unit / integration / smoke / e2e
.github/workflows/     CI (lint → tests → security), PyPI publish, E2E dispatch
```

### 6-Stage Pipeline (`src/clipsmith/pipeline.py`)

`process_vod()` runs sequentially; each stage writes a checkpoint file so `--resume` can skip completed work:

1. **Download** — `twitch-dl` subprocess → `work/<vod_id>/<vod_id>.mp4`
2. **Detect webcam** — OpenCV Haar cascade → `webcam_rect.json` (optional)
3. **Transcribe** — `faster-whisper` with parallel chunking → `transcript.json`
4. **Chat** — GQL replay download → `chat.json`
5. **Candidates** — 5-signal scoring (existing clips +100, !clip commands +25, chat density peaks, hype keywords +20, audio energy RMS +15); deduped within 60s → `candidates.json`
6. **LLM selection** — Top-N candidates sent to LLM → `picks.json`; then FFmpeg renders → `out/<vod_id>/`

### Package Layout

| Package | Responsibility |
|---|---|
| `cli/` | Typer CLI commands (entry: `clipsmith.cli:app`) |
| `pipeline.py` | Orchestrates 6 stages, checkpoint system |
| `api/` | FastAPI app, routes, deps, background worker |
| `twitch/` | Helix API client, VOD downloader, chat replay, watcher daemon |
| `transcription/` | faster-whisper wrapper with chunked parallel processing |
| `candidates/` | 5-signal candidate detection and scoring |
| `selection/` | LLM provider calls and result filtering |
| `rendering/` | FFmpeg clip cutting, captions (ASS), 9:16 reframing |
| `llm/` | Provider abstraction (Anthropic, OpenAI, Ollama) behind `ClipPicker` Protocol |
| `models/` | Pure dataclasses — `Transcript`, `CandidateMoment`, `ChatMessage`, `Video`, `Clip` |
| `config/` | Pydantic schemas (`AppConfig` + sub-models), YAML + `.env` loaders |
| `db/` | SQLAlchemy ORM: `Run`, `Clip`, `PipelineEvent` (SQLite) |
| `cloud/` | Azure Container Instances lifecycle + Google Drive upload |
| `publish/` | YouTube OAuth2 upload |
| `telemetry.py` | OTel tracer/meter init + Prometheus instruments; no-op fallbacks when `[observability]` not installed |

### FastAPI API (`src/clipsmith/api/`)

- `app.py` — App factory with lifespan (config load, DB init, OTel FastAPI instrumentation), CORS
- `routes/runs.py` — POST /runs (validates `vod_id` regex), GET list/detail
- `routes/clips.py` — GET clips per run, PATCH approve/title (increments CLIPS_APPROVED/REJECTED)
- `routes/stream.py` — SSE progress stream (`/runs/{id}/progress`)
- `routes/files.py` — Clip file downloads
- `routes/health.py` — GET /health, GET /metrics (Prometheus scrape), GET /stats (JSON run counts)
- `deps.py` — `get_db()` session, `verify_api_key()` header check
- `worker.py` — `BackgroundTasks` runner; OTel stage spans + STAGE_DURATION histogram; RUNS_TOTAL counter

### Next.js Dashboard (`web/`)

- `app/api/[...path]/route.ts` — **Server-side API proxy**: forwards all methods to FastAPI and injects `X-Api-Key` from `process.env.API_KEY` (not exposed to the browser)
- `lib/api.ts` — Two base URLs: `PROXY=/api` for JSON calls (through proxy), `DIRECT=NEXT_PUBLIC_API_BASE` for SSE and file downloads
- `lib/types.ts` — `Run`, `Clip`, `PipelineEvent`, `RunStatus`, `RunCreate`
- `app/page.tsx` — Dashboard: polls runs every 5s while any run is active

### LLM Provider Pattern

`llm/` uses a `ClipPicker` Protocol so backends are swappable. The Anthropic provider (default) uses **prompt caching** — the system prompt and stream context are cached per VOD to reduce cost. Configured via `config.yaml` `llm.provider`.

### Test Organization

Tests use four pytest markers gating test scope:

- `unit` — No I/O, fast
- `integration` — Mocked external services or subprocesses
- `smoke` — CLI runner or real YAML/config parsing
- `e2e` — Full pipeline against real infrastructure (skipped by default; requires `--run-e2e`)

### Configuration

`config.yaml` controls runtime behavior (clip bounds, LLM provider/model, transcription model, candidate weights, caption/reframe settings). `load_config()` reads YAML; `load_secrets()` reads `.env` via pydantic-settings. Copy `.env.example` → `.env` to set API keys.

### Observability Stack

`src/clipsmith/telemetry.py` is the single init point. Import it once (side-effect) at server startup — `api/app.py` does this via `from ..telemetry import tracer`.

| Instrument | Type | Labels |
|-----------|------|--------|
| `clipsmith_runs_total` | Prometheus Counter | `status` (done/failed) |
| `clipsmith_clips_approved_total` | Prometheus Counter | — |
| `clipsmith_clips_rejected_total` | Prometheus Counter | — |
| `clipsmith_stage_duration_seconds` | Prometheus Histogram | `stage` |
| `clipsmith_llm_call_duration_seconds` | Prometheus Histogram | `provider` |
| `clipsmith.llm.calls_total` | OTel Counter | `provider`, `outcome` |
| `clipsmith.llm.call_duration_seconds` | OTel Histogram | `provider` |

Local dev stack (Prometheus + Grafana + Jaeger):
```bash
docker compose -f docker-compose.observability.yml up -d
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 clipsmith serve
# Prometheus: http://localhost:9090
# Jaeger:     http://localhost:16686
# Grafana:    http://localhost:3001  (admin / $GRAFANA_ADMIN_PASSWORD, default: admin)
```

Production: set `APPLICATIONINSIGHTS_CONNECTION_STRING` to forward traces to Azure Monitor.

### CI Pipeline

`.github/workflows/ci.yml`: lint (ruff + mypy) → tests (pytest, no e2e) → security (bandit + pip-audit). PyPI publish is tag-triggered via OIDC trusted publisher.
