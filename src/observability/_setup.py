"""OpenTelemetry configuration for distributed tracing, metrics, and logging."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.metrics import Meter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Tracer

logger = logging.getLogger(__name__)

_setup_done = False
_setup_lock = threading.Lock()


def setup_telemetry(service_name: str, otlp_endpoint: str | None = None, *, app: Any | None = None) -> None:
    global _setup_done
    with _setup_lock:
        if _setup_done:
            return

        resource = Resource.create({SERVICE_NAME: service_name})

        tracer_provider = TracerProvider(resource=resource)
        if otlp_endpoint:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
        else:
            tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        trace.set_tracer_provider(tracer_provider)

        metric_exporter = (
            OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True) if otlp_endpoint else ConsoleMetricExporter()
        )
        metric_reader = PeriodicExportingMetricReader(metric_exporter)
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        from opentelemetry import metrics as otel_metrics

        otel_metrics.set_meter_provider(meter_provider)

        logger_provider = LoggerProvider(resource=resource)
        if otlp_endpoint:
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(OTLPLogExporter(endpoint=otlp_endpoint, insecure=True)),
            )
        else:
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(ConsoleLogExporter()),
            )
        from opentelemetry import _logs as otel_logs

        otel_logs.set_logger_provider(logger_provider)

        handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
        logging.root.addHandler(handler)

        if app is not None:
            FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()

        _setup_done = True
    logger.info("OpenTelemetry initialized for service=%s, endpoint=%s", service_name, otlp_endpoint)


def instrument_sqlalchemy(engine: Any) -> None:
    if not SQLAlchemyInstrumentor().is_instrumented_by_opentelemetry:
        SQLAlchemyInstrumentor().instrument(engine=engine)


def get_tracer(name: str) -> Tracer:
    return trace.get_tracer(name)


def get_meter(name: str) -> Meter:
    from opentelemetry import metrics as otel_metrics

    return otel_metrics.get_meter(name)


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, str | int | float] | None = None,
) -> Iterator[trace.Span]:
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(name) as span:
        if attributes:
            span.set_attributes(attributes)
        yield span
