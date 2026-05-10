# Dev Setup

## Install

```sh
git clone https://github.com/ricardogr07/clipsmith
cd clipsmith
pip install -e ".[dev]"
pip install -e ".[vision]"   # optional — for detect-webcam and OpenCV tests
pip install -e ".[server]"   # optional — for REST API server (FastAPI + uvicorn)
```

## Run the API server

```sh
pip install -e ".[server]"
clipsmith serve
# → http://localhost:8000/docs
```

Set `api_key` in `config.yaml` (or env var `CLIPSMITH_API_KEY`) to require an
`X-Api-Key` header on mutating endpoints. Leave it `null` to disable auth
(default for local dev).

## Run tests

```sh
pytest tests/ -q
```

The test suite has 142+ tests and runs in ~2 s. Core pipeline logic has >96% coverage.
No external services are called — all LLM and Twitch API calls are mocked.

## Type checking

```sh
mypy src/
```

Strict mode is off; `disallow_untyped_defs = true` is enforced. Must report
`Success: no issues found` before merging.

## Linting

```sh
ruff check src tests
```

Line length: 100. Target: Python 3.11.

## Security scanning

```sh
bandit -r src/ -ll -x tests/
pip-audit
```

Both run in CI. `bandit` must report `No issues identified`. `pip-audit` flags known CVEs
in the installed environment.

## CI

Three separate workflow files in `.github/workflows/`:

| Workflow | Trigger | Jobs |
|---|---|---|
| `ci.yml` | every push / PR / manual | `lint` (ruff + mypy), `tests` (pytest), `security` (bandit + pip-audit) |
| `e2e.yml` | manual (`workflow_dispatch`) only | Twitch + Anthropic end-to-end pipeline |
| `e2e-cloud.yml` | manual (`workflow_dispatch`) only | Azure provisioning smoke tests |

E2E workflows are not triggered automatically — run them manually before a release.

## Docs

```sh
pip install -e ".[dev]"   # includes mkdocs + mkdocs-material
mkdocs serve              # live-reload at http://127.0.0.1:8000
mkdocs build --strict     # production build, fails on warnings
```

Doc source lives in `docs/`. The site config is `mkdocs.yml` at the repo root.

## Module layout

```
src/clipsmith/
├── api/
│   ├── __init__.py
│   ├── app.py             FastAPI app factory — CORS, lifespan, router assembly
│   ├── deps.py            get_db(), verify_api_key() shared dependencies
│   ├── worker.py          Background thread: runs process_vod, emits SSE events
│   └── routes/
│       ├── runs.py        POST/GET /runs, GET /runs/{id}
│       ├── clips.py       GET /runs/{id}/clips, PATCH /clips/{id}
│       ├── stream.py      GET /runs/{id}/progress  (SSE)
│       ├── files.py       GET /clips/file/{filename}
│       └── health.py      GET /health, GET /metrics
├── db/
│   ├── __init__.py
│   ├── models.py          SQLAlchemy ORM: Run, Clip, PipelineEvent
│   └── session.py         Engine init, get_session(), init_db()
├── cli/
│   ├── __init__.py     Typer app assembly — registers all command groups
│   ├── run.py          process, watch, run-vod, whoami
│   ├── clip.py         clip, reframe
│   ├── setup.py        setup, check-ollama, detect-webcam
│   ├── cloud.py        cloud setup|build|run|drive-auth|status
│   └── utils.py        _resolve_config, _parse_start_at
├── cloud/
│   ├── azure_runner.py ACI container lifecycle + file share I/O
│   ├── drive_upload.py Google Drive OAuth2 upload
│   └── provisioner.py  Ephemeral resource group + storage account per run
├── config/
│   ├── models.py       AppConfig, CloudConfig, ClipConfig, … (Pydantic)
│   └── loaders.py      load_config(), load_secrets(), Secrets
├── twitch/
│   ├── client.py       Twitch API (user ID lookup, existing clips)
│   ├── downloader.py   twitch-dl wrapper
│   ├── chat.py         GQL chat replay download
│   ├── state.py        Persists seen VOD IDs
│   └── watcher.py      Poll daemon
├── transcription/
│   └── transcriber.py  faster-whisper wrapper (chunked parallel)
├── candidates/
│   ├── builder.py      Signal merging and scoring
│   ├── math.py         Sliding-window density + peak detection
│   └── audio.py        ffmpeg RMS energy extraction
├── selection/
│   └── selector.py     LLM loop → PickResult list
├── rendering/
│   ├── clipper.py      ffmpeg clip cutting + ASS caption burn-in
│   ├── captions.py     Transcript → ASS subtitle file
│   └── detect.py       OpenCV Haar cascade webcam detection
├── llm/
│   ├── base.py         ClipPicker Protocol, ClipPick dataclass
│   ├── prompts.py      System prompt + candidate prompt builders
│   ├── anthropic_provider.py
│   ├── openai_provider.py
│   └── ollama_provider.py
├── models/
│   ├── transcript.py   Transcript, Segment dataclasses
│   ├── chat.py         ChatLog dataclass
│   ├── candidates.py   Candidate dataclass
│   └── twitch.py       TwitchClip dataclass
├── io/
│   └── media.py        Video metadata helpers
├── pipeline.py         Orchestrator — calls stages 1-6
└── settings.py         Re-export shim for AppConfig + Secrets
```

## Adding a new LLM provider

1. Create `src/clipsmith/llm/<name>_provider.py` implementing the `ClipPicker` Protocol
   from `src/clipsmith/llm/base.py`.
2. Add a branch in `src/clipsmith/selection/selector.py` where providers are instantiated.
3. Add the provider name to the `--provider` help strings in `src/clipsmith/cli/run.py` and `src/clipsmith/cli/setup.py`.
4. Write tests in `tests/test_selector.py` mocking the new provider.
