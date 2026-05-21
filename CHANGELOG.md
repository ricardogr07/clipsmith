# Changelog

## [Unreleased]

### Sprints 1–7 — Full-Stack AI Pipeline (post-0.2.1)

All changes below were developed as portfolio sprints after the 0.2.1 release. They
transform the CLI tool into a production-grade, full-stack AI content pipeline.

#### Sprint 7 — Observability Stack

* Add `src/clipsmith/telemetry.py`: OpenTelemetry tracer/meter init and shared
  Prometheus instruments with graceful no-op fallbacks when `[observability]` not installed
* Instrument pipeline stages: `pipeline.run` root OTel span with per-stage child spans;
  `clipsmith_stage_duration_seconds` Prometheus histogram
* Instrument LLM providers (Anthropic, OpenAI, Ollama): `llm.call` OTel spans with
  provider/model attributes; `clipsmith_llm_call_duration_seconds` histogram and
  `clipsmith_llm_calls_total` counter
* Add `GET /metrics` Prometheus scrape endpoint; rename former JSON endpoint to `GET /stats`
* Add `CLIPS_APPROVED` / `CLIPS_REJECTED` Prometheus counters on clip approval
* Add `docker-compose.observability.yml`: 4-service local stack (otel-collector, Jaeger,
  Prometheus, Grafana on port 3001)
* Add `infra/grafana/dashboards/clipsmith.json`: pre-built dashboard with 5 panels
  (runs stat, approval gauge, stage p95 bar, LLM latency timeseries, approval rate)
* Add `[observability]` extra to `pyproject.toml` (opentelemetry-sdk/api,
  prometheus-client, azure-monitor-opentelemetry-exporter)
* Add Azure Monitor / Application Insights OTLP export via `APPLICATIONINSIGHTS_CONNECTION_STRING`

#### Sprint 6 — Infrastructure as Code

* Add `infra/modules/` Terraform modules: storage, registry (ACR), keyvault, network
* Add `infra/environments/dev.tfvars` and `prod.tfvars`
* Migrate container image from Docker Hub to Azure Container Registry (ACR)
* Inject Azure Key Vault secret references into ACI env at container-create time
* Add `terraform fmt -check` + `terraform validate` to CI lint job

#### Sprint 5 — ML Feedback Loop

* Add `signal_breakdown` JSON column on `Clip`: per-signal score contributions at harvest time
* Add `prompt_version` field on `Run`: tracks which prompt template was used
* Add `GET /analytics/signals`: per-signal approval rate across all reviewed clips
* Add `GET /analytics/prompts`: approval rate grouped by prompt version and LLM provider
* Add `POST /analytics/runs/{id}/calibrate`: recompute and persist signal weights
* Add second prompt template (`v2`) in `llm/prompts.py` for A/B comparison
* Add `RunCreate.prompt_version` field for dashboard prompt template selection
* Integrate Postman collection for API testing; publish OpenAPI spec improvements

#### Security Hardening

* Add `X-Api-Key` authentication on all mutating endpoints (`POST /runs`, `PATCH /clips`,
  `POST /clips/{id}/publish`, `POST /analytics/runs/{id}/calibrate`)
* Validate `vod_id` against strict regex; sanitise all path inputs
* Configure CORS with explicit allowed origins via `CORS_ORIGINS` env var

#### Sprint 4 — Publishing + Polish

* Add `src/clipsmith/publish/youtube.py`: YouTube Shorts upload for approved clips
* Add `POST /clips/{id}/publish` → stores result URL in DB
* Add multi-language support: `language: auto` in config
* Enforce rate limiting: 1 concurrent pipeline run per server instance

#### Sprint 3 — Observability + Pipeline Reliability

* Add `structlog` JSON logging with `run_id` / `vod_id` context binding throughout pipeline
* Add stage sentinel files: skip completed stages on `--resume`
* Add `retry_pick()` wrapper: 3 attempts, 2s/4s exponential backoff on LLM failures

#### Sprint 2 — Next.js Dashboard + Auth

* Add `web/` Next.js 16 App Router dashboard for live clip review
* Server-side API proxy (`web/app/api/[...path]/route.ts`) injects `X-Api-Key`
* Live SSE progress stream via `ProgressStream` component
* Cypress E2E tests, Storybook component library, Jest unit tests

#### Sprint 1 — REST API Layer + SQLite Persistence

* Add `src/clipsmith/db/`: SQLAlchemy ORM models `Run`, `Clip`, `PipelineEvent`
* Add `src/clipsmith/api/`: FastAPI application with full REST API
* Add `clipsmith serve` CLI command to start the API server
* Add SSE endpoint for real-time pipeline progress streaming
* Add background worker with `BackgroundTasks`; prevents concurrent runs via `app.state.active_run_id`

---

## [0.2.1](https://github.com/ricardogr07/clipsmith/compare/v0.2.0...v0.2.1) (2026-05-09)


### Bug Fixes

* use pip install clipsmith-ai in all Colab notebooks ([#3](https://github.com/ricardogr07/clipsmith/issues/3)) ([6eedef5](https://github.com/ricardogr07/clipsmith/commit/6eedef5d7ed4724741d969ebf1b882e3718be489))

## [0.2.0](https://github.com/ricardogr07/clipsmith/compare/v0.1.0...v0.2.0) (2026-05-09)


### Features

* add --local flag to skip Twitch API calls for offline runs ([f7a2dd1](https://github.com/ricardogr07/clipsmith/commit/f7a2dd1c3662ca8dee8245c612284addb2a7b7cf))
* add process and setup commands for non-technical users ([78a6b80](https://github.com/ricardogr07/clipsmith/commit/78a6b8087c0a0b34012be5e8375486d515849e6b))
* add PyInstaller spec, Windows build script, and user README ([ec4ac9a](https://github.com/ricardogr07/clipsmith/commit/ec4ac9aa240beb8d248c526e8f04173e406ec6ac))
* add reframe=none stream-copy and transcript-sample fallback ([5d2f84c](https://github.com/ricardogr07/clipsmith/commit/5d2f84cf5457d1817b2727f923c9a4bbbc1321e4))
* PyPI distribution as clipsmith-ai with release-please and OIDC publish ([42673c4](https://github.com/ricardogr07/clipsmith/commit/42673c449d69bd38bb24fe74a13d101d5fcfa428))
* replace chat_downloader with direct Twitch GQL pagination ([44933e7](https://github.com/ricardogr07/clipsmith/commit/44933e79b628ffead0307672bf26b89aeac8c670))
* two-path .env discovery and bundled ffmpeg detection ([d10d6b6](https://github.com/ricardogr07/clipsmith/commit/d10d6b6482eeb9aeca4f619cf38a87b9cec9b72d))


### Bug Fixes

* install ffmpeg in tests job; upgrade pip and skip editable in pip-audit ([a570434](https://github.com/ricardogr07/clipsmith/commit/a570434e23aa14608f2e80f7169e97dccc7bf353))


### Documentation

* add ARCHITECTURE.md with pipeline diagram and module map ([ef554eb](https://github.com/ricardogr07/clipsmith/commit/ef554eb4999dc41e3f9c8032c3363e0ebb08f454))
* add Artifacts section to architecture.md ([e0a0b37](https://github.com/ricardogr07/clipsmith/commit/e0a0b37d151a0323b631a7d985d464c40f1bc78d))
* add MkDocs site with Material theme ([0765f6e](https://github.com/ricardogr07/clipsmith/commit/0765f6e9b9849a6b947d9a1e0a7d768476f8e0b3))
* refresh all docs, add SP setup, replace Colab notebook ([41c9faf](https://github.com/ricardogr07/clipsmith/commit/41c9faf3c0ea76994a00dd83f38a9124e5d2f3d1))
* refresh architecture, add cloud guide, update commands and configuration ([4b50d2d](https://github.com/ricardogr07/clipsmith/commit/4b50d2d1a7065f8e1484827c4a0580df027f48e2))
