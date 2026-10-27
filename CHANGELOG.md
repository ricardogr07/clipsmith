# Changelog

## [0.3.0](https://github.com/ricardogr07/clipsmith/compare/v0.2.1...v0.3.0) (2026-06-26)


### Features

* ACI start/stop toggle workflow + stable DNS hostname ([#23](https://github.com/ricardogr07/clipsmith/issues/23)) ([70e3c1b](https://github.com/ricardogr07/clipsmith/commit/70e3c1b51959babc2b8b8052c1cb8cd93d98a67c))
* add cloud/start_s/end_s to New Run dialog + toggle stop guard ([#25](https://github.com/ricardogr07/clipsmith/issues/25)) ([ac2b3f5](https://github.com/ricardogr07/clipsmith/commit/ac2b3f55f4a771e338623d92fed4ea3f80c24040))
* add teardown option to toggle workflow ([#36](https://github.com/ricardogr07/clipsmith/issues/36)) ([32caacf](https://github.com/ricardogr07/clipsmith/commit/32caacfe170fd6dd2dae8437657c3bf03bb5195f))
* GitHub Actions as single Vercel deploy source + maintenance mode ([#24](https://github.com/ricardogr07/clipsmith/issues/24)) ([0f9c038](https://github.com/ricardogr07/clipsmith/commit/0f9c03810919824bd73d1984e1d94ffd7f5da410))
* mount Azure File Shares for persistent DB and clips storage ([#26](https://github.com/ricardogr07/clipsmith/issues/26)) ([fc7864a](https://github.com/ricardogr07/clipsmith/commit/fc7864a76a08b933e1d4b1222705e69e13eabfb3))
* Spanish Colab notebook + Drive save with clip selection ([#6](https://github.com/ricardogr07/clipsmith/issues/6)) ([24a58bc](https://github.com/ricardogr07/clipsmith/commit/24a58bc5997c2612c5ee05e1e7c5b9d68e8157d6))
* Sprint 1 — FastAPI REST layer + SQLite persistence ([#7](https://github.com/ricardogr07/clipsmith/issues/7)) ([0f64418](https://github.com/ricardogr07/clipsmith/commit/0f644181c0cfdc71a888687b96c1987852b461c9))
* Sprint 12 — Stage 6 Managed Identity + persistent ACI auth + delete failed run UI ([#20](https://github.com/ricardogr07/clipsmith/issues/20)) ([4d0af6f](https://github.com/ricardogr07/clipsmith/commit/4d0af6f4a2b21ee3200b9c732396fd98672d8c6e))
* Sprint 2 — Next.js 16 dashboard ([#9](https://github.com/ricardogr07/clipsmith/issues/9)) ([ea7b0be](https://github.com/ricardogr07/clipsmith/commit/ea7b0bebde1a40dc2975738a2a3698260a9f13f0))
* Sprint 3 — Observability + Pipeline Reliability ([#11](https://github.com/ricardogr07/clipsmith/issues/11)) ([858f447](https://github.com/ricardogr07/clipsmith/commit/858f447735585942fcc0f1da1bbf3af8a0698638))
* Sprint 4 — Publishing + Polish ([#12](https://github.com/ricardogr07/clipsmith/issues/12)) ([4d48e73](https://github.com/ricardogr07/clipsmith/commit/4d48e7367944da1b67714dee1b75b4434fb5e855))
* Sprint 5 — ML feedback loop + API docs + Postman collection ([#15](https://github.com/ricardogr07/clipsmith/issues/15)) ([46fde5c](https://github.com/ricardogr07/clipsmith/commit/46fde5cb53173d0bea3c6fc015bb05648fad5ac3))
* Sprint 6 — Terraform IaC, ACR, and Key Vault ([#16](https://github.com/ricardogr07/clipsmith/issues/16)) ([4524d15](https://github.com/ricardogr07/clipsmith/commit/4524d15f146b4c385ceaebe7f8805a0f5a550f04))
* Sprint 7 — Observability Stack (OpenTelemetry + Prometheus + Grafana) ([bc2f13e](https://github.com/ricardogr07/clipsmith/commit/bc2f13ec6638253068a8ccc61c904b65deedc22f))
* Sprint 8 — Run Detail UI + keyboard nav + signal breakdown ([#18](https://github.com/ricardogr07/clipsmith/issues/18)) ([4a9d11d](https://github.com/ricardogr07/clipsmith/commit/4a9d11dbeaae93bcf50d4cf19be44881daa4bd1c))
* Sprint 9 — Alembic migrations + DATABASE_URL abstraction ([#19](https://github.com/ricardogr07/clipsmith/issues/19)) ([bb85e56](https://github.com/ricardogr07/clipsmith/commit/bb85e56dd2097f29ef23d9cca0b486e40587fab7))


### Bug Fixes

* add --os-type Linux to az container create in deploy.yml ([#21](https://github.com/ricardogr07/clipsmith/issues/21)) ([7bf108d](https://github.com/ricardogr07/clipsmith/commit/7bf108df3444c501737ffaca343ee9b9465f7642))
* allow deleting any non-active run via DELETE /runs/{id} ([#32](https://github.com/ricardogr07/clipsmith/issues/32)) ([29d6470](https://github.com/ricardogr07/clipsmith/commit/29d64706298366148a61d1566795e3af93f9cc45))
* clip videos blocked by mixed-content + binary corruption in proxy ([#34](https://github.com/ricardogr07/clipsmith/issues/34)) ([820cba2](https://github.com/ricardogr07/clipsmith/commit/820cba2ce539a6d0259a5b191ac9e58e0e4f8856))
* cloud clips always 0 + quality guardrails for LLM selection ([#31](https://github.com/ricardogr07/clipsmith/issues/31)) ([3002191](https://github.com/ricardogr07/clipsmith/commit/30021918772f51d5ed95c8c3bac4d62da4976a2f))
* create app data/work/out dirs with clipsmith ownership + robust IP/health wait ([#22](https://github.com/ricardogr07/clipsmith/issues/22)) ([f15fa2f](https://github.com/ricardogr07/clipsmith/commit/f15fa2fa3ef426363b34ae403ac857a4cf98dbd6))
* extend health check to 360s and use FQDN (avoids race on image pull) ([#27](https://github.com/ricardogr07/clipsmith/issues/27)) ([667155b](https://github.com/ricardogr07/clipsmith/commit/667155b7006ec33424d8cbc77bd617cb94b62a29))
* guard teardown against concurrent Deploy + release SMB locks ([#37](https://github.com/ricardogr07/clipsmith/issues/37)) ([44d4706](https://github.com/ricardogr07/clipsmith/commit/44d470686af0bf73d5bd1e22aadb5af4aac6daa1))
* install Azure CLI before pip to prevent azure.mgmt namespace corruption ([#28](https://github.com/ricardogr07/clipsmith/issues/28)) ([da86175](https://github.com/ricardogr07/clipsmith/commit/da86175c8d2d338bdec07afd92880a006e6c4627))
* proxy drops range headers and buffers video — breaks playback ([#35](https://github.com/ricardogr07/clipsmith/issues/35)) ([b521c60](https://github.com/ricardogr07/clipsmith/commit/b521c60fe04fb7a9fe4539fdb1d99d9de54e8ea0))
* remove Azure CLI from image — provisioner uses Python SDK only ([#29](https://github.com/ricardogr07/clipsmith/issues/29)) ([349df5c](https://github.com/ricardogr07/clipsmith/commit/349df5ce0dd6841015cbdf93ad90242e8d51f3ca))
* security hardening — API auth, input validation, path safety, CORS ([#13](https://github.com/ricardogr07/clipsmith/issues/13)) ([539b73e](https://github.com/ricardogr07/clipsmith/commit/539b73e637600b459c6a66615e6f97a6e8658d7b))
* SSE stream disconnects during long cloud runs ([#33](https://github.com/ricardogr07/clipsmith/issues/33)) ([5df65e9](https://github.com/ricardogr07/clipsmith/commit/5df65e98a54b92b7b61ffcf6bfd00ef59c45076b))
* stream upstream.body directly and pass through range headers. ([b521c60](https://github.com/ricardogr07/clipsmith/commit/b521c60fe04fb7a9fe4539fdb1d99d9de54e8ea0))
* update ResourceManagementClient import path for azure-mgmt-resource v26 ([#30](https://github.com/ricardogr07/clipsmith/issues/30)) ([046d96a](https://github.com/ricardogr07/clipsmith/commit/046d96a29c70e8ecd957ec7cf56e916190027f08))
* use PAT for release-please so tag pushes trigger publish workflow ([#4](https://github.com/ricardogr07/clipsmith/issues/4)) ([50e0610](https://github.com/ricardogr07/clipsmith/commit/50e0610cb5aa739a6769e44f9ac8aa031645ff2d))

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
