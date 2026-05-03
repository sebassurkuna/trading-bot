"""OpenTelemetry tracing setup for the MT5 Bridge API."""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

logger = logging.getLogger(__name__)


def configure_otel(app, otel_endpoint: str | None = None) -> None:
    """Configure OpenTelemetry tracing and instrument the FastAPI application.

    When `otel_endpoint` is provided, spans are exported via OTLP/gRPC to a
    collector (e.g. Jaeger, Grafana Tempo). Otherwise traces are silently
    discarded, which is safe for local development without a collector.

    Args:
        app:           The FastAPI application instance to instrument.
        otel_endpoint: OTLP gRPC endpoint, e.g. 'http://localhost:4317'.
                       Leave None or empty to disable export.
    """
    provider = TracerProvider()

    if otel_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OpenTelemetry: exporting spans to %s", otel_endpoint)
        except ImportError:
            logger.warning(
                "opentelemetry-exporter-otlp-proto-grpc is not installed. "
                "Falling back to ConsoleSpanExporter."
            )
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        logger.info("OpenTelemetry: OTEL_ENDPOINT not set — spans will be discarded.")

    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls="metrics,health",
    )
