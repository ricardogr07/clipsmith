# Sprint 4 — Publishing + Polish

## Goal

Close the loop on the portfolio narrative by shipping **YouTube Shorts publishing**
for approved clips, making the pipeline **language-agnostic** (auto-detect instead
of hardcoded Spanish), and polishing the **API surface** for presentation quality.

Four features land together because they reinforce each other: publishing requires
the `published_url` DB column and a new route; multi-language extends both
transcription config and the candidate scorer; OpenAPI polish makes the new
`/publish` endpoint look as good as the rest; and rate limiting protects the
server from concurrent runs during a live demo.

---

## Step 0 — Doc Pre-flight

Sprint 3 is done. Update the plan doc before starting implementation.

### `docs/dev/PLAN.md`

| Item | Change |
|------|--------|
| Sprint 3 status | `🚧 In Progress` → `✅ Done` |
| Sprint 4 status | `🔜 Planned` → `🚧 In Progress` |

### Acceptance

- `PLAN.md` sprint map is accurate
- `mkdocs build --strict` passes with zero warnings

---

## Step 1 — Multi-language Support

Replace the hardcoded `language: es` and the module-level `_HYPE_KEYWORDS` frozenset
with config-driven values so any streamer's language and keyword set can be changed
in `config.yaml` without touching source code.

### `src/clipsmith/config/models.py`

Change `TranscribeConfig.language` default from `"es"` to `"auto"`:

```python
class TranscribeConfig(BaseModel):
    model: str = "medium"
    compute_type: str = "int8"
    language: str = "auto"  # "auto" → pass language=None to faster-whisper
    chunk_minutes: int = 0
    chunk_overlap_s: int = 30
    max_workers: int = 4
```

Add `hype_keywords` to `CandidatesConfig`:

```python
class CandidatesConfig(BaseModel):
    density_window_s: int = 15
    density_peak_multiplier: float = 4.0
    existing_clip_boost: float = 100.0
    clip_command_boost: float = 25.0
    dedupe_window_s: int = 60
    transcript_hype_score: float = 12.0
    audio_energy_enabled: bool = True
    audio_energy_window_s: float = 2.0
    audio_energy_peak_multiplier: float = 2.0
    audio_energy_boost: float = 15.0
    hype_keywords: list[str] = [
        "jaja", "jeje", "jajaj", "jajaja", "lmao", "lol", "xd", "xdd",
        "omg", "wow", "nooo", "noooo", "increíble", "increible",
        "tremendo", "brutal", "dios", "wtf", "carajo", "caray",
        "bestia", "monstro",
    ]
```

### `src/clipsmith/transcription/transcriber.py`

In `_transcribe_chunk()`, change the `language=` kwarg:

```python
# before
raw_segments, _ = model.transcribe(
    str(wav_path),
    language=config.language,
    ...
)

# after
lang = None if config.language == "auto" else config.language
raw_segments, _ = model.transcribe(
    str(wav_path),
    language=lang,
    ...
)
```

faster-whisper accepts `language=None` to trigger automatic detection per segment.

### `src/clipsmith/candidates/builder.py`

Remove the module-level block:

```python
# DELETE lines 26–51:
_HYPE_KEYWORDS = frozenset({
    "jaja", "jeje", ...
})
```

In Signal 4 (transcript hype), replace `_HYPE_KEYWORDS` with the config value:

```python
# before
kw_hits = sum(1 for kw in _HYPE_KEYWORDS if kw in text)

# after
_kw = frozenset(kw.lower() for kw in config.hype_keywords)
kw_hits = sum(1 for kw in _kw if kw in text)
```

Build `_kw` once before the loop (not per segment):

```python
if transcript is not None:
    _kw = frozenset(kw.lower() for kw in config.hype_keywords)
    for seg in transcript.segments:
        text = seg.text.lower()
        kw_hits = sum(1 for kw in _kw if kw in text)
        ...
```

### `config.yaml` additions

```yaml
transcribe:
  model: small
  compute_type: int8
  language: auto          # "auto" detects per-stream; set "es" / "en" to force
  chunk_minutes: 30
  chunk_overlap_s: 30
  max_workers: 4

candidates:
  # ... existing numeric settings ...
  hype_keywords:
    - jaja
    - jeje
    - jajaj
    - jajaja
    - lmao
    - lol
    - xd
    - xdd
    - omg
    - wow
    - nooo
    - noooo
    - increíble
    - increible
    - tremendo
    - brutal
    - dios
    - wtf
    - carajo
    - caray
    - bestia
    - monstro
```

---

## Step 2 — YouTube Shorts Publishing

Expose approved clips to YouTube Shorts via the YouTube Data API v3.
The upload URL is stored in a new `published_url` column on `Clip` and surfaced
through a REST endpoint and a CLI command.

### `pyproject.toml` — new `[publish]` extra

`google-api-python-client` and `google-auth-oauthlib` already appear in the
`[cloud]` extra. Extract them into a standalone `[publish]` extra so users
who only want publishing don't pull Azure SDKs:

```toml
[project.optional-dependencies]
publish = [
    "google-api-python-client>=2",
    "google-auth-oauthlib>=1",
]
cloud = [
    "azure-mgmt-resource>=23",
    "azure-mgmt-containerinstance>=10",
    "azure-mgmt-storage>=21",
    "azure-storage-file-share>=12",
    "azure-identity>=1.16",
    "clipsmith-ai[publish]",   # cloud always includes publish
]
```

### New module: `src/clipsmith/publish/__init__.py`

Empty — marks `publish` as a package.

### New module: `src/clipsmith/publish/youtube.py`

```python
"""YouTube Data API v3 upload helper for Shorts."""
from __future__ import annotations

from pathlib import Path


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubePublisher:
    def __init__(self, credentials_file: str, token_file: str) -> None:
        self._credentials_file = credentials_file
        self._token_file = Path(token_file)

    def _get_service(self):
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise ImportError(
                "YouTube publishing requires: pip install 'clipsmith-ai[publish]'"
            ) from exc

        creds = None
        if self._token_file.exists():
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_file(str(self._token_file), SCOPES)

        if not creds or not creds.valid:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(self._credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
            self._token_file.write_text(creds.to_json())

        from googleapiclient.discovery import build
        return build("youtube", "v3", credentials=creds)

    def upload(
        self,
        video_path: Path,
        *,
        title: str,
        description: str = "",
        privacy: str = "private",
        category_id: int = 20,
    ) -> str:
        """Upload a clip as a YouTube Short. Returns the watch URL."""
        from googleapiclient.http import MediaFileUpload

        svc = self._get_service()
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": str(category_id),
                "tags": ["#Shorts"],
            },
            "status": {"privacyStatus": privacy},
        }
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        response = (
            svc.videos()
            .insert(part="snippet,status", body=body, media_body=media)
            .execute()
        )
        return f"https://youtube.com/watch?v={response['id']}"
```

### `src/clipsmith/db/models.py`

Add `published_url` to `Clip` and include it in `to_dict()`:

```python
class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("runs.id"), index=True)
    filename: Mapped[str] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(String(256), default="")
    start_s: Mapped[float] = mapped_column(Float, default=0.0)
    end_s: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    published_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    run: Mapped[Run] = relationship(back_populates="clips")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "filename": self.filename,
            "title": self.title,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "score": self.score,
            "approved": self.approved,
            "published_url": self.published_url,
            "created_at": self.created_at.isoformat(),
        }
```

`Base.metadata.create_all(engine, checkfirst=True)` (called by `init_db()`) adds
the column on the next server start — no manual migration needed for a dev SQLite DB.

### `src/clipsmith/config/models.py` — `PublishConfig`

```python
class PublishConfig(BaseModel):
    youtube_credentials: str = "credentials.json"
    youtube_token: str = ".youtube_token.json"
    youtube_privacy: Literal["private", "unlisted", "public"] = "private"
    youtube_category: int = 20  # 20 = Gaming
```

Add to `AppConfig`:

```python
class AppConfig(BaseModel):
    # ... existing fields ...
    publish: PublishConfig = PublishConfig()
```

### `config.yaml` addition

```yaml
publish:
  youtube_credentials: credentials.json   # OAuth2 client secret from Google Cloud Console
  youtube_token: .youtube_token.json      # cached token (auto-created on first upload)
  youtube_privacy: private                # private | unlisted | public
  youtube_category: 20                    # 20 = Gaming
```

### New route: `src/clipsmith/api/routes/publish.py`

```python
"""Publishing endpoints."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db
from ...db.models import Clip
from ...publish.youtube import YouTubePublisher
from ...settings import load_config

router = APIRouter(tags=["publish"])


@router.post(
    "/clips/{clip_id}/publish",
    summary="Publish an approved clip to YouTube Shorts",
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
    video_path = cfg.out_dir.expanduser() / clip.filename
    if not video_path.exists():
        raise HTTPException(404, f"Clip file not found on disk: {clip.filename}")

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
```

### `src/clipsmith/api/app.py`

Register the publish router:

```python
from .routes import clips, files, health, publish, runs, stream

# ...
app.include_router(publish.router)
```

### CLI publish command — `src/clipsmith/cli/clip.py`

Add `publish_cmd` function:

```python
def publish_cmd(
    clip_id: int = typer.Argument(..., help="DB clip ID to upload"),
) -> None:
    """Upload an approved clip from the DB to YouTube Shorts."""
    from ..db.session import init_db, get_session
    from ..db.models import Clip as ClipModel

    cfg = load_config(Path("config.yaml"))
    db_path = cfg.work_dir.expanduser() / "clipsmith.db"
    init_db(db_path)
    db = get_session()
    try:
        clip = db.get(ClipModel, clip_id)
        if not clip:
            console.print(f"[red]Clip {clip_id} not found in DB.[/red]")
            raise typer.Exit(1)
        if not clip.approved:
            console.print("[red]Clip must be approved before publishing.[/red]")
            raise typer.Exit(1)
        if clip.published_url:
            console.print(f"[yellow]Already published:[/yellow] {clip.published_url}")
            return

        from ..publish.youtube import YouTubePublisher
        publisher = YouTubePublisher(
            credentials_file=cfg.publish.youtube_credentials,
            token_file=cfg.publish.youtube_token,
        )
        video_path = cfg.out_dir.expanduser() / clip.filename
        url = publisher.upload(
            video_path,
            title=clip.title or clip.filename,
            privacy=cfg.publish.youtube_privacy,
            category_id=cfg.publish.youtube_category,
        )
        clip.published_url = url
        db.commit()
        console.print(f"[green]Published:[/green] {url}")
    finally:
        db.close()
```

Register in `src/clipsmith/cli/__init__.py`:

```python
from .clip import clip_cmd, publish_cmd, reframe_cmd

app.command("publish")(publish_cmd)
```

---

## Step 3 — OpenAPI Polish

Add `summary=` and docstrings to every route handler so the auto-generated
`/docs` UI shows a clean, readable API reference.

### `src/clipsmith/api/routes/runs.py`

```python
@router.post("", status_code=201, summary="Create a pipeline run")
def create_run(...) -> dict:
    """Start an async pipeline run for the given VOD ID. Returns the new run record."""

@router.get("", summary="List all runs")
def list_runs(...) -> list[dict]:
    """Return all pipeline runs ordered by creation time descending."""

@router.get("/{run_id}", summary="Get a run by ID")
def get_run(...) -> dict:
    """Return a single run record. 404 if not found."""
```

### `src/clipsmith/api/routes/clips.py`

```python
@router.get("/runs/{run_id}/clips", summary="List clips for a run")
def list_clips(...) -> list[dict]:
    """Return all clips produced by the given run. 404 if run not found."""

@router.patch("/clips/{clip_id}", summary="Approve or reject a clip")
def patch_clip(...) -> dict:
    """Set approved=true/false on a clip. 404 if clip not found."""
```

### `src/clipsmith/api/routes/stream.py`

```python
@router.get("/runs/{run_id}/progress", summary="Stream pipeline progress (SSE)")
def stream_progress(...) -> StreamingResponse:
    """Server-Sent Events stream of PipelineEvent rows for the given run.
    Closes automatically when the run reaches done or failed status."""
```

### `src/clipsmith/api/routes/files.py`

```python
@router.get("/runs/{run_id}/clips/file/{filename}", summary="Download a clip file")
def serve_clip(...) -> FileResponse:
    """Serve the MP4 clip file associated with the given run and filename."""
```

### `src/clipsmith/api/routes/health.py`

```python
@router.get("/health", summary="Health check")
def health(...) -> dict:
    """Return server and database status. Always 200; check 'db' field for DB health."""

@router.get("/metrics", summary="Run metrics")
def metrics(...) -> dict:
    """Return pipeline run counts grouped by status (pending/running/done/failed)."""
```

---

## Step 4 — Rate Limiting (1 Concurrent Run)

Track the active run ID in `app.state` so `POST /runs` rejects new requests
while a pipeline is in progress. No external dependencies needed.

### `src/clipsmith/api/app.py`

Initialise the state flag in `_lifespan`:

```python
@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    cfg = load_config(Path("config.yaml"))
    db_path = cfg.work_dir.expanduser() / "clipsmith.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db(db_path)
    app.state.active_run_id = None  # int | None; cleared by worker on completion
    yield
```

### `src/clipsmith/api/routes/runs.py`

Inject `Request` and check the flag before creating a run:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

@router.post("", status_code=201, summary="Create a pipeline run")
def create_run(
    body: RunCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """Start an async pipeline run for the given VOD ID. Returns the new run record.

    Returns 429 if a run is already in progress on this server.
    """
    if request.app.state.active_run_id is not None:
        raise HTTPException(429, "A pipeline run is already in progress")
    run = Run(vod_id=body.vod_id, channel=body.channel, status=RunStatus.pending)
    db.add(run)
    db.commit()
    db.refresh(run)
    request.app.state.active_run_id = run.id
    background_tasks.add_task(
        start_run, run.id, body.vod_id, body.channel, body.provider, request.app
    )
    return run.to_dict()
```

### `src/clipsmith/api/worker.py`

`start_run()` accepts the `app` object and clears `active_run_id` in `finally`:

```python
def start_run(
    run_id: int, vod_id: str, channel: str, provider: str | None, app
) -> None:
    """Entry point for BackgroundTasks. Opens its own DB session for thread safety."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(run_id=run_id, vod_id=vod_id)
    db = get_session()
    try:
        _run_pipeline(db, run_id, vod_id, channel, provider)
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
        app.state.active_run_id = None
```

---

## File Layout (final state after Sprint 4)

```
clipsmith/
├── src/clipsmith/
│   ├── publish/
│   │   ├── __init__.py              NEW
│   │   └── youtube.py               NEW — YouTubePublisher
│   ├── candidates/
│   │   └── builder.py               MODIFIED — remove _HYPE_KEYWORDS; use config.hype_keywords
│   ├── transcription/
│   │   └── transcriber.py           MODIFIED — language=None when config.language == "auto"
│   ├── config/
│   │   └── models.py                MODIFIED — PublishConfig; hype_keywords in CandidatesConfig; language default "auto"
│   ├── db/
│   │   └── models.py                MODIFIED — Clip.published_url + to_dict()
│   ├── api/
│   │   ├── app.py                   MODIFIED — include publish router; app.state.active_run_id in lifespan
│   │   ├── worker.py                MODIFIED — start_run() gains app param; clears flag in finally
│   │   └── routes/
│   │       ├── runs.py              MODIFIED — 429 rate limit; Request param; summaries
│   │       ├── clips.py             MODIFIED — summaries
│   │       ├── stream.py            MODIFIED — summary
│   │       ├── files.py             MODIFIED — summary
│   │       ├── health.py            MODIFIED — summaries
│   │       └── publish.py           NEW — POST /clips/{id}/publish
│   └── cli/
│       ├── __init__.py              MODIFIED — register publish command
│       └── clip.py                  MODIFIED — publish_cmd function
├── pyproject.toml                   MODIFIED — [publish] extra; [cloud] references [publish]
├── config.yaml                      MODIFIED — transcribe.language; candidates.hype_keywords; publish section
└── docs/dev/
    ├── PLAN.md                      MODIFIED — Sprint 3 done, Sprint 4 active (Step 0)
    ├── sprint1.md                   Unchanged
    ├── sprint2.md                   Unchanged
    ├── sprint3.md                   Unchanged
    └── sprint4.md                   This file
```

---

## Verification Checklist

### Step 0 — Docs
- [ ] `PLAN.md` shows Sprint 3 `✅ Done` and Sprint 4 `🚧 In Progress`
- [ ] `mkdocs build --strict` exits 0

### Step 1 — Multi-language
- [ ] `transcribe.language: auto` in `config.yaml` results in `language=None` passed to faster-whisper
- [ ] `transcribe.language: en` results in `language="en"` (explicit override works)
- [ ] `hype_keywords` list in `config.yaml` is used by `build_candidates()`; adding a new word causes it to score
- [ ] `_HYPE_KEYWORDS` symbol no longer exists in `builder.py` (no import, no frozenset literal)
- [ ] Existing unit tests for candidate builder pass with the new config-driven keywords

### Step 2 — YouTube Publishing
- [ ] `clipsmith publish <clip_id>` opens a browser OAuth flow on first run; saves token to `.youtube_token.json`
- [ ] Subsequent `publish` calls reuse the token file (no browser prompt)
- [ ] On a machine without `google-api-python-client`, `YouTubePublisher.upload()` raises `ImportError` with an install hint
- [ ] `GET /runs/{id}/clips` JSON includes `published_url: null` before publish and the watch URL after
- [ ] `POST /clips/{id}/publish` on an unapproved clip → 422
- [ ] `POST /clips/{id}/publish` on an already-published clip → 200 with existing URL (idempotent)
- [ ] `POST /clips/{id}/publish` when clip file is missing on disk → 404

### Step 3 — OpenAPI
- [ ] `GET /docs` shows a summary and description on every route
- [ ] All six route files (`runs`, `clips`, `stream`, `files`, `health`, `publish`) have `summary=` on every handler
- [ ] `GET /` still redirects to `/docs`

### Step 4 — Rate Limiting
- [ ] `POST /runs` while a run is active → 429 `"A pipeline run is already in progress"`
- [ ] After the active run reaches `done` or `failed`, the next `POST /runs` succeeds
- [ ] Server restart resets the flag to `None` (expected — intentionally not persisted)
