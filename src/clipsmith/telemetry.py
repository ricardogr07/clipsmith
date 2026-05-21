"""OpenTelemetry tracer/meter initialisation and shared Prometheus instruments.

Import this module once at startup (side-effect import in api/app.py) to configure the
SDK before any spans or metrics are recorded.

When the [observability] extra is not installed the module loads silently with no-op
objects so the rest of the codebase never needs to guard against ImportError.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator


# ── No-op stubs (used when packages are absent) ───────────────────────────────


class _NoopSpan:
    def end(self) -> None: ...
    def set_attribute(self, key: str, value: Any) -> None: ...


@contextmanager
def _noop_ctx(*_: Any, **__: Any) -> Generator[_NoopSpan, None, None]:
    yield _NoopSpan()


class _NoopTracer:
    def start_as_current_span(self, name: str, **kwargs: Any) -> Any:
        return _noop_ctx()

    def start_span(self, name: str, **kwargs: Any) -> _NoopSpan:
        return _NoopSpan()


class _NoopInstrument:
    def record(self, *_: Any, **__: Any) -> None: ...
    def add(self, *_: Any, **__: Any) -> None: ...


class _NoopLabels:
    def inc(self) -> None: ...
    def observe(self, *_: Any) -> None: ...


class _NoopCounter:
    def labels(self, **_: Any) -> _NoopLabels:
        return _NoopLabels()

    def inc(self) -> None: ...


class _NoopHistogram:
    def labels(self, **_: Any) -> _NoopLabels:
        return _NoopLabels()

    def observe(self, *_: Any) -> None: ...


# ── Attempt real initialisation ───────────────────────────────────────────────

try:
    from opentelemetry import metrics as _otel_metrics, trace as _otel_trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        ConsoleMetricExporter,
        PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    _SERVICE_NAME = "clipsmith"
    _resource = Resource.create({"service.name": _SERVICE_NAME})

    _tracer_provider = TracerProvider(resource=_resource)

    _otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if _otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        _tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=_otlp_endpoint))
        )
    else:
        _tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    _az_conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if _az_conn:
        from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter  # type: ignore[import]

        _tracer_provider.add_span_processor(
            BatchSpanProcessor(AzureMonitorTraceExporter(connection_string=_az_conn))
        )

    _otel_trace.set_tracer_provider(_tracer_provider)
    tracer: Any = _otel_trace.get_tracer(_SERVICE_NAME)

    if _otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.metrics_exporter import OTLPMetricExporter

        _metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=_otlp_endpoint), export_interval_millis=60_000
        )
    else:
        _metric_reader = PeriodicExportingMetricReader(
            ConsoleMetricExporter(), export_interval_millis=60_000
        )
    _meter_provider = MeterProvider(resource=_resource, metric_readers=[_metric_reader])
    _otel_metrics.set_meter_provider(_meter_provider)
    _meter = _otel_metrics.get_meter(_SERVICE_NAME)

    stage_duration: Any = _meter.create_histogram(
        "clipsmith.pipeline.stage_duration_seconds",
        description="Wall-clock time per pipeline stage",
        unit="s",
    )
    llm_call_duration: Any = _meter.create_histogram(
        "clipsmith.llm.call_duration_seconds",
        description="LLM API round-trip time per candidate",
        unit="s",
    )
    llm_calls_total: Any = _meter.create_counter(
        "clipsmith.llm.calls_total",
        description="Total LLM calls labelled by provider and include/skip outcome",
    )
    candidates_scored_total: Any = _meter.create_counter(
        "clipsmith.candidates.scored_total",
        description="Total candidate moments scored per run",
    )

    _OTEL_AVAILABLE = True

except ImportError:
    tracer = _NoopTracer()
    stage_duration = _NoopInstrument()
    llm_call_duration = _NoopInstrument()
    llm_calls_total = _NoopInstrument()
    candidates_scored_total = _NoopInstrument()
    _OTEL_AVAILABLE = False


# ── Prometheus instruments ────────────────────────────────────────────────────

try:
    from prometheus_client import Counter, Histogram

    RUNS_TOTAL: Any = Counter(
        "clipsmith_runs_total",
        "Pipeline runs completed",
        ["status"],
    )
    CLIPS_APPROVED: Any = Counter(
        "clipsmith_clips_approved_total",
        "Clips approved via the dashboard",
    )
    CLIPS_REJECTED: Any = Counter(
        "clipsmith_clips_rejected_total",
        "Clips rejected via the dashboard",
    )
    STAGE_DURATION: Any = Histogram(
        "clipsmith_stage_duration_seconds",
        "Pipeline stage wall-clock time",
        ["stage"],
        buckets=[10, 30, 60, 120, 300, 600, 1200, 3600],
    )
    LLM_CALL_DURATION: Any = Histogram(
        "clipsmith_llm_call_duration_seconds",
        "LLM API round-trip time per candidate",
        ["provider"],
        buckets=[0.5, 1, 2, 5, 10, 20, 30, 60],
    )

except ImportError:
    RUNS_TOTAL = _NoopCounter()
    CLIPS_APPROVED = _NoopCounter()
    CLIPS_REJECTED = _NoopCounter()
    STAGE_DURATION = _NoopHistogram()
    LLM_CALL_DURATION = _NoopHistogram()
