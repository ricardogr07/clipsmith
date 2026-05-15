# Sprint 1 — REST API Layer + SQLite Persistence

## Goal

Replace scattered JSON files with a proper database and expose the pipeline as an HTTP API. This unlocks the frontend (Sprint 2) and every other enhancement.

## Files Created

```
src/clipsmith/
├── db/
│   ├── __init__.py
│   ├── models.py          SQLAlchemy ORM: Run, Clip, PipelineEvent
│   └── session.py         Engine init, get_session(), init_db()
└── api/
    ├── __init__.py
    ├── app.py             FastAPI app, CORS, lifespan (DB init)
    ├── deps.py            get_db() dependency
    ├── worker.py          Background thread: runs process_vod, emits events
    └── routes/
        ├── __init__.py
        ├── runs.py        POST/GET /runs, GET /runs/{id}
        ├── clips.py       GET /runs/{id}/clips, PATCH /clips/{id}
        ├── stream.py      GET /runs/{id}/progress  (SSE)
        ├── files.py       GET /clips/file/{filename}
        └── health.py      GET /health, GET /metrics
```

## Files Modified

| File | Change |
|------|--------|
| `src/clipsmith/pipeline.py` | Added optional `on_stage(stage, pct)` callback parameter |
| `src/clipsmith/cli/run.py` | Added `serve` command (starts uvicorn) |
| `src/clipsmith/cli/__init__.py` | Registered `serve` command |
| `pyproject.toml` | Added `[server]` optional-dependencies extra |

## Database Schema

```sql
CREATE TABLE runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vod_id      TEXT NOT NULL,
    channel     TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending|running|done|failed
    stage       TEXT,
    error       TEXT,
    created_at  DATETIME NOT NULL,
    updated_at  DATETIME NOT NULL
);

CREATE TABLE clips (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    filename    TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    start_s     REAL NOT NULL DEFAULT 0.0,
    end_s       REAL NOT NULL DEFAULT 0.0,
    score       REAL NOT NULL DEFAULT 0.0,
    approved    BOOLEAN,
    created_at  DATETIME NOT NULL
);

CREATE TABLE pipeline_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    stage       TEXT NOT NULL,
    pct         REAL NOT NULL,
    message     TEXT NOT NULL DEFAULT '',
    created_at  DATETIME NOT NULL
);
```

## API Contract

```
POST   /runs                         201 { id, vod_id, status: "pending" }
GET    /runs                         200 [ Run, ... ]
GET    /runs/{id}                    200 Run
GET    /runs/{id}/progress           200 text/event-stream (SSE PipelineEvents)
GET    /runs/{id}/clips              200 [ Clip, ... ]
PATCH  /clips/{id}                   200 Clip  (body: { approved: bool })
GET    /clips/file/{filename}        200 video/mp4 FileResponse
GET    /health                       200 { status, db, version }
GET    /metrics                      200 { runs_by_status }
GET    /docs                         OpenAPI UI (FastAPI auto-generated)
GET    /                             302 → /docs
```

## Pipeline Stage Callbacks

`on_stage(stage, pct)` is called at these points in `process_vod`:

| Stage | pct | Point in pipeline |
|-------|-----|-------------------|
| `download` | 5 | before VOD download |
| `transcribe` | 15 | before transcription |
| `chat` | 40 | before chat download |
| `candidates` | 50 | before candidate scoring |
| `select` | 60 | before LLM selection |
| `clip` | 85 | before ffmpeg cutting |

## Install

```bash
pip install -e ".[server]"
clipsmith serve
# → http://localhost:8000/docs
```

## Verification Checklist

- [ ] `clipsmith serve` → uvicorn on :8000, `/docs` loads OpenAPI UI
- [ ] `POST /runs {"vod_id": "..."}` → 201, run appears in DB
- [ ] `GET /runs/{id}` → status transitions: pending → running → done
- [ ] `GET /runs/{id}/progress` (SSE) → events stream live during pipeline
- [ ] `GET /runs/{id}/clips` → list of clips with titles and scores
- [ ] `PATCH /clips/{id}` `{"approved": true}` → persisted in SQLite
- [ ] `GET /clips/file/clip_01_xxx.mp4` → video file served
- [ ] `GET /health` → 200 `{"status":"ok","db":"ok","version":"0.2.1"}`
- [ ] `GET /metrics` → run counts by status
- [ ] `GET /` → redirects to `/docs`
