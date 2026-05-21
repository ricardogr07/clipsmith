# clipsmith — Portfolio Enhancement Roadmap

## Vision

Transform clipsmith from a CLI tool into a **production-grade, full-stack AI content pipeline** that showcases the complete senior-engineer skill set: FastAPI + React full-stack, cloud infrastructure as code, MLOps feedback loops, operational observability, and continuous deployment.

**Portfolio narrative:** *"Built an end-to-end AI video production system: multi-signal candidate detection → LLM-based selection with prompt caching → human-in-the-loop approval → automatic signal calibration based on approval history → YouTube publishing. Fully instrumented with OpenTelemetry traces and Prometheus metrics, deployed via CI/CD to Azure, and reprovisioned through Terraform."*

---

## Sprint Map

| Sprint | Theme | Key Deliverable | Status |
|--------|-------|-----------------|--------|
| 1 | REST API + DB | `clipsmith serve`, FastAPI, SQLite, SSE progress | ✅ Done |
| 2 | Next.js Dashboard | Live clip review UI, auth gate, progress streaming | ✅ Done |
| 2.1 | Testing | Cypress E2E, Storybook, component tests | ✅ Done |
| 3 | Reliability | Structured logs, stage checkpoints, LLM retry | ✅ Done |
| 4 | Publishing + Polish | YouTube Shorts, multi-language, OpenAPI polish | ✅ Done |
| Security | Hardening | API auth, input validation, path safety, CORS | ✅ Done |
| 5 | ML Feedback Loop | Signal calibration, prompt A/B, approval analytics | ✅ Done |
| 6 | Infrastructure as Code | Terraform modules, Key Vault, ACR | ✅ Done |
| 7 | Observability Stack | OpenTelemetry traces, Prometheus metrics, Grafana | 🚧 In Progress |
| 8 | Run Detail UI | Video player, keyboard shortcuts, signal charts | 🔜 Planned |
| 9 | DB Migrations | Alembic, DATABASE_URL abstraction, PostgreSQL | 🔜 Planned |
| 10 | Continuous Deployment | deploy.yml, ACI update, health-check gate | 🔜 Planned |

---

## Sprints 1–4 (Completed)

### Sprint 1 — REST API Layer + SQLite Persistence

**Goal:** Replace scattered JSON files with a proper database and expose the pipeline as an HTTP API.

**Deliverables:**
- `src/clipsmith/db/` — SQLAlchemy models: `Run`, `Clip`, `PipelineEvent`
- `src/clipsmith/api/` — FastAPI app with full REST API
- `clipsmith serve` CLI command to start the server
- SSE endpoint for real-time pipeline progress

**See:** [sprint1.md](sprint1.md) · **Status:** ✅ Done

---

### Sprint 2 — Next.js Dashboard + Auth

**Goal:** Live web dashboard for clip review.

**See:** [sprint2.md](sprint2.md) · **Status:** ✅ Done

---

### Sprint 3 — Observability + Pipeline Reliability

**Goal:** Production-trustworthy pipeline. Structured logs, stage checkpoints, LLM retry.

**Deliverables:**
- `structlog` JSON logging with `run_id` context binding
- Stage sentinel files: skip completed stages on resume
- `retry_pick()` wrapper: 3 attempts, 2s/4s exponential backoff

**See:** [sprint3.md](sprint3.md) · **Status:** ✅ Done

---

### Sprint 4 — Publishing + Polish

**Goal:** End-to-end social publishing and API presentation quality.

**Deliverables:**
- `src/clipsmith/publish/youtube.py` — YouTube Shorts upload for approved clips
- `POST /clips/{id}/publish` → stores result URL in DB
- Multi-language: `language: auto` in config
- Rate limiting: 1 concurrent run per server

**See:** [sprint4.md](sprint4.md) · **Status:** ✅ Done

---

## Sprint 5 — ML Feedback Loop

**Goal:** Turn the approval DB into a learning signal. Track which candidate signals actually predict good clips, calibrate their weights over time, and A/B test prompt templates.

**Deliverables:**
- `signal_breakdown` JSON column on `Clip`: per-signal score contributions captured at harvest time
- `prompt_version` field on `Run`: tracks which prompt template was used
- `GET /analytics/signals` — per-signal approval rate across all reviewed clips
- `GET /analytics/prompts` — approval rate grouped by prompt version and LLM provider
- `POST /runs/{id}/calibrate` — recompute and persist signal weights after approval
- Second prompt template (`v2`) in `llm/prompts.py` for A/B comparison
- `RunCreate.prompt_version` field so the dashboard can select prompt template

**See:** [sprint5.md](sprint5.md) · **Status:** 🔜 Next

---

## Sprint 6 — Infrastructure as Code

**Goal:** Replace ad-hoc ACI provisioning with reproducible Terraform. Move all secrets to Azure Key Vault. Push images to Azure Container Registry instead of Docker Hub.

**Deliverables:**
- `infra/modules/` — Terraform modules: storage, registry (ACR), keyvault, network
- `infra/environments/dev.tfvars` and `prod.tfvars`
- ACR integration in `azure_runner.py` (pull image from ACR, not Docker Hub)
- Key Vault secret references injected into ACI env at container-create time
- `terraform fmt -check` + `terraform validate` added to CI lint job

**See:** [sprint6.md](sprint6.md) · **Status:** ✅ Done

---

## Sprint 7 — Observability Stack

**Goal:** Instrument the pipeline with OpenTelemetry distributed traces, expose Prometheus metrics, and provide a local Docker Compose stack (Prometheus + Grafana + Jaeger) with a pre-built dashboard.

**Deliverables:**
- OpenTelemetry spans for every pipeline stage, LLM call, and FFmpeg operation
- `GET /metrics` in Prometheus text format (stage durations, LLM latency, approval rates)
- `docker-compose.observability.yml` — Prometheus, Grafana, OTLP Collector, Jaeger
- `infra/grafana/clipsmith-dashboard.json` — importable Grafana dashboard
- Azure Monitor / Application Insights OTLP export for production

**See:** [sprint7.md](sprint7.md) · **Status:** 🚧 In Progress

---

## Sprint 8 — Run Detail UI + Video Player

**Goal:** Complete the pending run-detail page with an in-browser video player, real-time SSE progress bar, approve/reject keyboard shortcuts, and signal breakdown mini-charts.

**Deliverables:**
- `web/app/runs/[id]/page.tsx` — complete server + client split
- `web/components/ProgressStream.tsx` — SSE hook → animated stage progress bar
- `web/components/ClipCard.tsx` — lazy `<video>` player, approve/reject, signal breakdown bar
- Keyboard navigation: arrow keys to select clip, J = approve, K = reject, Space = play/pause
- Signal breakdown bar chart per clip (uses `signal_breakdown` from Sprint 5)

**See:** [sprint8.md](sprint8.md) · **Status:** 🔜 Planned

---

## Sprint 9 — Database Migrations + PostgreSQL

**Goal:** Replace `create_all(checkfirst=True)` with proper Alembic migrations and abstract the connection string to support PostgreSQL in production alongside SQLite for local/CI.

**Deliverables:**
- `alembic/` directory with `env.py` reading `DATABASE_URL`
- `DATABASE_URL` env var in `db/session.py` (default: `sqlite:///./work/clipsmith.db`)
- Initial migration covering the full schema (Sprints 1–5 columns)
- CI runs `alembic upgrade head` before pytest
- `docs/configuration.md` updated with DATABASE_URL section

**See:** [sprint9.md](sprint9.md) · **Status:** 🔜 Planned

---

## Sprint 10 — Continuous Deployment

**Goal:** Close the CI/CD loop. On every merge to `main`, build and push the Docker image to ACR, update the persistent `clipsmith-api` ACI instance, and verify the deployment with a `/health` gate before marking success.

**Deliverables:**
- `.github/workflows/deploy.yml` — build → push to ACR → update ACI → health-check gate
- Rollback: re-deploy previous image SHA on health-check failure
- Manual approval gate for promotion from dev to prod ACI instance
- `deploy.yml` matrix variable for dev vs prod environment

**See:** [sprint10.md](sprint10.md) · **Status:** 🔜 Planned

---

## Architecture Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| DB | SQLite + SQLAlchemy + Alembic | Zero-ops for solo dev; Alembic enables PostgreSQL promotion |
| API | FastAPI | Auto OpenAPI docs, type-safe, async support |
| SSE | Sync generator + StreamingResponse | Simple, no Redis/WebSocket overhead |
| Frontend | Next.js 16 App Router | Most current React pattern; server proxy hides API key |
| Styling | Tailwind + shadcn/ui | Fast to build, polished output |
| Cloud execution | Azure ACI | Ephemeral, billed per-second; no Kubernetes overhead |
| IaC | Terraform | Industry standard; state enables drift detection |
| Secrets | Azure Key Vault | Secrets not in env vars or CI logs |
| Registry | Azure Container Registry | Private, co-located with ACI; no Docker Hub rate limits |
| Traces | OpenTelemetry | Vendor-neutral; exports to Jaeger locally, Azure Monitor in prod |
| Metrics | Prometheus | Standard scrape format; pairs with Grafana |
| Migrations | Alembic | Production-grade schema evolution for SQLAlchemy |
| CD | GitHub Actions → ACI update | Integrates with existing CI; no separate CD platform needed |

---

## What the Full Roadmap Delivers

| Dimension | After Sprints 1–4 | After Sprints 5–10 |
|-----------|-------------------|---------------------|
| AI/ML | Prompt engineering | Prompt A/B + signal weight calibration |
| Observability | Structured logs | Logs + traces + metrics + Grafana dashboard |
| Infrastructure | Ad-hoc ACI scripts | Terraform IaC + Key Vault + ACR |
| Database | SQLite, `create_all` | Alembic migrations + PostgreSQL-ready |
| Frontend | Dashboard + empty detail page | Full clip review UI with video player |
| Deployment | Manual push | CI → build → push → deploy → health-check |
| Portfolio story | "I built a pipeline" | "I operate a production AI system" |
