# clipsmith — Portfolio Enhancement Roadmap

## Vision

Transform clipsmith from a CLI tool into a **full-stack AI content pipeline** that showcases:

- FastAPI REST backend with real-time SSE progress streaming
- Next.js dashboard for clip review and approval
- SQLite persistence (proper DB, not scattered JSON)
- Structured observability and pipeline reliability
- End-to-end social publishing (YouTube Shorts)

**Portfolio narrative:** *"Built a full-stack AI video platform — FastAPI + SQLite backend, Next.js dashboard, real-time progress streaming, and multi-LLM clip selection from Twitch VODs."*

---

## Sprint Map

| Sprint | Weekend | Theme | Key Deliverable |
|--------|---------|-------|-----------------|
| 1 | Weekend 1 | REST API + DB | `clipsmith serve`, FastAPI, SQLite, SSE progress |
| 2 | Weekend 2 | Next.js Dashboard | Live clip review UI, auth gate, modal player, more options |
| 3 | Weekend 3 | Reliability | Structured logs, stage checkpointing, LLM retry |
| 4 | Weekend 4 | Publishing | YouTube Shorts upload, multi-language, API polish |

---

## Sprint 1 — REST API Layer + SQLite Persistence

**Goal:** Replace scattered JSON files with a proper database and expose the pipeline as an HTTP API.

**Deliverables:**
- `src/clipsmith/db/` — SQLAlchemy models: `Run`, `Clip`, `PipelineEvent`
- `src/clipsmith/api/` — FastAPI app with full REST API
- `clipsmith serve` CLI command to start the server
- SSE endpoint for real-time pipeline progress

**API Contract:** See [sprint1.md](sprint1.md).

**Status:** ✅ Done

---

## Sprint 2 — Next.js Dashboard + Auth

**Goal:** Live web dashboard for clip review, secured by an API key gate.

**Architecture:**
```
web/                        Next.js 14 App Router
├── app/
│   ├── page.tsx            Dashboard: run list + "New Run" dialog
│   └── runs/[id]/page.tsx  Run detail: SSE progress bar + clip grid
├── components/
│   ├── RunCard.tsx         Status chip, VOD ID, clip count
│   ├── ClipCard.tsx        Thumbnail row + approve/reject + "Details" toggle
│   ├── ClipMoreOptions.tsx Expanded panel: title edit, score bar, timestamps
│   ├── ClipModal.tsx       Full-viewport video modal with metadata
│   ├── NewRunDialog.tsx    Form: vod_id + channel + provider select
│   └── ProgressStream.tsx  SSE hook → live stage + percentage bar
└── lib/api.ts              Typed fetch wrappers; injects X-Api-Key header
```

**Key decisions:**
- Next.js 14 App Router (not Pages Router)
- Tailwind + shadcn/ui (card, badge, button, progress, dialog)
- API proxy: `/api/*` → `http://localhost:8000` (avoids CORS on SSE stream)
- Video served by FastAPI `FileResponse` at `GET /clips/file/{filename}`
- API key: static `X-Api-Key` header; key stored in `NEXT_PUBLIC_API_KEY` env var
- Only mutating endpoints (`POST /runs`, `PATCH /clips/{id}`) require the key

**See:** [sprint2.md](sprint2.md)

**Status:** ✅ Done

---

## Sprint 3 — Observability + Pipeline Reliability

**Goal:** Production-trustworthy pipeline. Structured logs, stage checkpoints, LLM retry.

**Deliverables:**
- `structlog` JSON logging with `run_id` context binding
- Stage sentinel files: skip completed stages on resume
- `retry_pick()` wrapper: 3 attempts, 2s/4s exponential backoff
- Schema validation on LLM JSON responses (required keys + offset clamping)
- `--resume` flag on `clipsmith run-vod`

**Status:** ✅ Done

---

## Sprint 4 — Publishing + Polish

**Goal:** End-to-end social publishing and API presentation quality.

**Deliverables:**
- `src/clipsmith/publish/youtube.py` — YouTube Shorts upload for approved clips
- `POST /clips/{id}/publish` → stores result URL in DB
- Multi-language: `language: auto` in config, hype keywords moved to `config.yaml`
- OpenAPI tags + descriptions on all routes, `GET /` → `/docs`
- Rate limiting on `POST /runs` (1 concurrent run per server)

**Status:** 🚧 In Progress

---

## Architecture Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| DB | SQLite + SQLAlchemy | Zero-ops, sufficient for solo/small team use, easy to show schema |
| API | FastAPI | Auto OpenAPI docs, type-safe, async support, de facto Python API standard |
| SSE | Sync generator + StreamingResponse | Simple, no Redis/WebSocket overhead |
| Frontend | Next.js 14 App Router | Most current React pattern, shows fullstack range |
| Styling | Tailwind + shadcn/ui | Fast to build, looks polished |
| Publishing | YouTube Data API v3 | Direct OAuth2 upload, no 3rd-party service dependency |

## What This Delivers

| Dimension | Before | After 4 sprints |
|-----------|--------|-----------------|
| Stack | Python CLI only | FastAPI + SQLite + Next.js |
| Frontend | Colab notebooks | Live web dashboard |
| Persistence | JSON files | SQLite (proper DB) |
| Real-time | None | SSE progress streaming |
| Observability | print/logging | Structured JSON logs + metrics |
| Reliability | No resume | Stage checkpoints + LLM retry |
| Publishing | Google Drive | YouTube Shorts via API |
| Language | Spanish hardcoded | Config-driven auto-detect |
