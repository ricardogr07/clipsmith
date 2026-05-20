# Sprint 7 — Observability Stack

## Goal

Instrument the pipeline with OpenTelemetry distributed traces, expose a Prometheus metrics
endpoint, and provide a local Docker Compose stack with Grafana dashboards so the full
observability story works out of the box. Connect to Azure Monitor for production.

Sprint 3 introduced structured logs. This sprint adds the other two pillars: **traces**
(causally linked spans across the pipeline stages) and **metrics** (aggregated counters and
histograms scraped by Prometheus). The three pillars together make it possible to answer
"what is slow?", "what is failing?", and "what is the approval trend?"

---

## Step 0 — Doc Pre-flight

### `docs/dev/PLAN.md`

| Item | Change |
|------|--------|
| Sprint 7 status | `🔜 Planned` → `🚧 In Progress` |

---

## Step 1 — Dependencies

### `pyproject.toml`

Add a new `[observability]` optional extra:

```toml
observability = [
    "opentelemetry-sdk>=1.24",
    "opentelemetry-api>=1.24",
    "opentelemetry-instrumentation-fastapi>=0.45b0",
    "opentelemetry-instrumentation-httpx>=0.45b0",
    "opentelemetry-exporter-otlp-proto-grpc>=1.24",
    "prometheus-client>=0.20",
]
```

Install for development:

```bash
pip install -e ".[dev,server,observability]"
```

---

## Step 2 — OpenTelemetry Instrumentation

### New file: `src/clipsmith/telemetry.py`

Central tracer setup — imported once at application startup.

```python
"""OpenTelemetry tracer and meter initialisation."""

from __future__ import annotations

import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.sdk.resources import Resource

_SERVICE_NAME = "clipsmith"
_resource = Resource.create({"service.name": _SERVICE_NAME})

# Tracer
_tracer_provider = TracerProvider(resource=_resource)

_otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
if _otlp_endpoint:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    _tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=_otlp_endpoint))
    )
else:
    # Console exporter for local dev without a collector
    _tracer_provider.add_span_processor(
        BatchSpanProcessor(ConsoleSpanExporter())
    )

trace.set_tracer_provider(_tracer_provider)
tracer = trace.get_tracer(_SERVICE_NAME)

# Meter
_metric_reader = PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=60_000)
_meter_provider = MeterProvider(resource=_resource, metric_readers=[_metric_reader])
metrics.set_meter_provider(_meter_provider)
meter = metrics.get_meter(_SERVICE_NAME)

# ── Instruments ───────────────────────────────────────────────────────────────

stage_duration = meter.create_histogram(
    "clipsmith.pipeline.stage_duration_seconds",
    description="Wall-clock time per pipeline stage",
    unit="s",
)

llm_call_duration = meter.create_histogram(
    "clipsmith.llm.call_duration_seconds",
    description="LLM API round-trip time per candidate",
    unit="s",
)

llm_calls_total = meter.create_counter(
    "clipsmith.llm.calls_total",
    description="Total LLM calls, labelled by provider and include/skip outcome",
)

clips_approved_total = meter.create_counter(
    "clipsmith.clips.approved_total",
    description="Clips approved via the dashboard",
)

clips_rejected_total = meter.create_counter(
    "clipsmith.clips.rejected_total",
    description="Clips rejected via the dashboard",
)

candidates_scored_total = meter.create_counter(
    "clipsmith.candidates.scored_total",
    description="Total candidate moments scored per run",
)
```

### `src/clipsmith/api/app.py`

Import the FastAPI auto-instrumentor in the lifespan:

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from ..telemetry import tracer  # noqa: F401 — side-effect import initialises SDK

@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    ...  # existing init
    FastAPIInstrumentor.instrument_app(app)
    yield
```

---

## Step 3 — Pipeline Stage Spans

Wrap each `process_vod` stage in an OTel span. The easiest integration point is the
existing `on_stage` callback — extend `worker.py` to open and close spans around
stage transitions.

### `src/clipsmith/api/worker.py`

```python
import time
from ..telemetry import tracer, stage_duration, candidates_scored_total

def _run_pipeline(db, run_id, vod_id, channel, provider, prompt_version="v1"):
    ...
    _stage_spans: dict[str, tuple] = {}  # stage → (span, start_time)

    def on_stage(stage: str, pct: float) -> None:
        # Close previous span if any
        prev_stage, prev_data = next(
            ((s, d) for s, d in _stage_spans.items()), (None, None)
        ) if _stage_spans else (None, None)
        if prev_stage and prev_data:
            prev_span, t0 = prev_data
            elapsed = time.monotonic() - t0
            stage_duration.record(elapsed, {"stage": prev_stage, "vod_id": vod_id})
            prev_span.end()
            del _stage_spans[prev_stage]

        # Open new span
        span = tracer.start_span(
            f"pipeline.{stage}",
            attributes={"run_id": run_id, "vod_id": vod_id, "stage": stage, "pct": pct},
        )
        _stage_spans[stage] = (span, time.monotonic())
        _emit(db, run_id, stage, pct)

    with tracer.start_as_current_span("pipeline.run", attributes={"run_id": run_id, "vod_id": vod_id}):
        process_vod(video, cfg, secrets, on_stage=on_stage)

    # Close final span
    for stage, (span, t0) in _stage_spans.items():
        stage_duration.record(time.monotonic() - t0, {"stage": stage, "vod_id": vod_id})
        span.end()
    ...
```

### LLM providers — timing and counters

In `anthropic_provider.py`, `openai_provider.py`, and `ollama_provider.py`, wrap each
API call:

```python
import time
from ..telemetry import tracer, llm_call_duration, llm_calls_total

# inside the pick() method, around the API call:
t0 = time.monotonic()
with tracer.start_as_current_span(
    "llm.call",
    attributes={"provider": "anthropic", "model": self._model},
):
    raw = self._client.messages.create(...)
elapsed = time.monotonic() - t0
outcome = "include" if pick.include else "skip"
llm_call_duration.record(elapsed, {"provider": "anthropic"})
llm_calls_total.add(1, {"provider": "anthropic", "outcome": outcome})
```

---

## Step 4 — Prometheus `/metrics` Endpoint

Expose a `GET /metrics` endpoint in Prometheus text format (not the JSON `GET /metrics`
that already exists — rename the existing endpoint to `GET /stats`).

### `src/clipsmith/api/routes/health.py`

```python
from prometheus_client import (
    Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
)
from fastapi.responses import Response

# Prometheus instruments (module-level so they persist)
RUNS_TOTAL = Counter("clipsmith_runs_total", "Pipeline runs started", ["status"])
CLIPS_APPROVED = Counter("clipsmith_clips_approved_total", "Clips approved")
CLIPS_REJECTED = Counter("clipsmith_clips_rejected_total", "Clips rejected")
STAGE_DURATION = Histogram(
    "clipsmith_stage_duration_seconds",
    "Pipeline stage wall-clock time",
    ["stage"],
    buckets=[10, 30, 60, 120, 300, 600, 1200, 3600],
)


@router.get("/metrics", response_class=Response, summary="Prometheus metrics scrape endpoint")
def prometheus_metrics() -> Response:
    """Return all metrics in Prometheus text format for scraping."""
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


@router.get("/stats", summary="Run status counts (JSON)")
def stats(db: Session = Depends(get_db)) -> dict:
    """Return pipeline run counts grouped by status."""
    ...  # existing /metrics handler body, renamed to /stats
```

Update `RUNS_TOTAL` in `worker.py` when a run starts and finishes:

```python
from ..api.routes.health import RUNS_TOTAL, STAGE_DURATION, CLIPS_APPROVED, CLIPS_REJECTED

# In start_run, on success:
RUNS_TOTAL.labels(status="done").inc()
# On failure:
RUNS_TOTAL.labels(status="failed").inc()
```

Update `CLIPS_APPROVED` / `CLIPS_REJECTED` in `clips.py` `patch_clip`:

```python
from ..routes.health import CLIPS_APPROVED, CLIPS_REJECTED

if body.approved:
    CLIPS_APPROVED.inc()
else:
    CLIPS_REJECTED.inc()
```

---

## Step 5 — Local Observability Stack (Docker Compose)

### `docker-compose.observability.yml`

```yaml
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.100.0
    command: ["--config=/etc/otel/config.yaml"]
    volumes:
      - ./infra/otel/collector-config.yaml:/etc/otel/config.yaml:ro
    ports:
      - "4317:4317"   # OTLP gRPC — set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
    depends_on:
      - jaeger
      - prometheus

  jaeger:
    image: jaegertracing/all-in-one:1.57
    ports:
      - "16686:16686"   # Jaeger UI
      - "14250:14250"   # gRPC for collector

  prometheus:
    image: prom/prometheus:v2.52.0
    volumes:
      - ./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"
    extra_hosts:
      - "host.docker.internal:host-gateway"   # scrape host's /metrics

  grafana:
    image: grafana/grafana:10.4.2
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=clipsmith
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
    volumes:
      - ./infra/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./infra/grafana/dashboards:/var/lib/grafana/dashboards:ro
    ports:
      - "3001:3000"
    depends_on:
      - prometheus
      - jaeger
```

### `infra/otel/collector-config.yaml`

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
  logging:
    verbosity: normal

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [jaeger, logging]
```

### `infra/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: clipsmith-api
    static_configs:
      - targets: ["host.docker.internal:8000"]
    metrics_path: /metrics
```

### `infra/grafana/provisioning/datasources/default.yaml`

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
  - name: Jaeger
    type: jaeger
    url: http://jaeger:16686
```

### `infra/grafana/dashboards/clipsmith.json`

A pre-built dashboard JSON with the following panels:

| Panel | Query | Visualisation |
|-------|-------|---------------|
| Runs started (24h) | `increase(clipsmith_runs_total[24h])` | Stat |
| Approval rate | `rate(clipsmith_clips_approved_total[1h]) / (rate(...approved...[1h]) + rate(...rejected...[1h]))` | Gauge |
| Stage duration p95 | `histogram_quantile(0.95, clipsmith_stage_duration_seconds_bucket)` | Bar chart by stage |
| LLM latency p50/p95 | `histogram_quantile(0.5, clipsmith_llm_call_duration_seconds_bucket)` | Time series |
| Clips approved/rejected | `rate(clipsmith_clips_approved_total[5m])` | Time series |

Commit the full JSON file to `infra/grafana/dashboards/clipsmith.json` (generated by
Grafana's "Export dashboard" feature after wiring up the queries manually once).

---

## Step 6 — Azure Monitor Integration (Production)

When `APPLICATIONINSIGHTS_CONNECTION_STRING` env var is set, forward traces to Azure
Monitor Application Insights via OTLP.

### `src/clipsmith/telemetry.py` (addition)

```python
az_conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if az_conn:
    from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
    _tracer_provider.add_span_processor(
        BatchSpanProcessor(AzureMonitorTraceExporter(connection_string=az_conn))
    )
```

Add to the `observability` extra:

```toml
"azure-monitor-opentelemetry-exporter>=1.0.0b21",
```

---

## File Layout (final state after Sprint 7)

```
src/clipsmith/
├── telemetry.py               NEW — OTel tracer/meter init; shared instruments
├── api/
│   ├── app.py                 MODIFIED — FastAPIInstrumentor.instrument_app()
│   ├── worker.py              MODIFIED — stage spans + RUNS_TOTAL counter
│   └── routes/
│       ├── health.py          MODIFIED — GET /metrics (Prometheus); GET /stats (former /metrics)
│       └── clips.py           MODIFIED — CLIPS_APPROVED / CLIPS_REJECTED counters
└── llm/
    ├── anthropic_provider.py  MODIFIED — llm span + llm_call_duration histogram
    ├── openai_provider.py     MODIFIED — same
    └── ollama_provider.py     MODIFIED — same

infra/
├── otel/
│   └── collector-config.yaml  NEW
├── prometheus/
│   └── prometheus.yml         NEW
└── grafana/
    ├── provisioning/
    │   └── datasources/default.yaml  NEW
    └── dashboards/
        └── clipsmith.json     NEW

docker-compose.observability.yml  NEW
pyproject.toml                    MODIFIED — [observability] extra
```

---

## Verification Checklist

### Local stack
- [ ] `docker compose -f docker-compose.observability.yml up -d` starts all four services
- [ ] Prometheus UI (`http://localhost:9090`) → Targets shows `clipsmith-api` as UP
- [ ] `GET http://localhost:8000/metrics` returns Prometheus text format (not JSON)
- [ ] `GET http://localhost:8000/stats` returns JSON run counts (renamed former /metrics)

### Traces
- [ ] Run a pipeline → Jaeger UI (`http://localhost:16686`) shows a `clipsmith` service
- [ ] Each pipeline stage appears as a child span under `pipeline.run`
- [ ] LLM calls appear as `llm.call` spans with `provider` and `model` attributes
- [ ] FastAPI HTTP requests appear as root spans (auto-instrumented)

### Metrics
- [ ] After approving a clip → `clipsmith_clips_approved_total` increments
- [ ] After a pipeline run → `clipsmith_runs_total{status="done"}` increments
- [ ] Stage durations populate `clipsmith_stage_duration_seconds_bucket`

### Grafana
- [ ] Grafana (`http://localhost:3001`) loads with anonymous viewer access
- [ ] Prometheus and Jaeger datasources show green health check
- [ ] Import `infra/grafana/dashboards/clipsmith.json` → all panels render data after one run

### Azure Monitor (production)
- [ ] With `APPLICATIONINSIGHTS_CONNECTION_STRING` set, traces appear in Application Insights → Transaction Search
