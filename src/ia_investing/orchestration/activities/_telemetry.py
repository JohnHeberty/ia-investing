from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

from opentelemetry import metrics, trace
from temporalio import activity


def get_activity_tracer() -> trace.Tracer:
    return trace.get_tracer("ia_investing.activities")


def get_activity_meter() -> metrics.Meter:
    return metrics.get_meter("ia_investing.activities")


_meter = get_activity_meter()
activity_runs = _meter.create_counter(
    name="activity_runs",
    description="Number of activity executions",
    unit="1",
)
activity_duration = _meter.create_histogram(
    name="activity_duration",
    description="Activity execution duration in milliseconds",
    unit="ms",
)
activity_errors = _meter.create_counter(
    name="activity_errors",
    description="Number of activity errors",
    unit="1",
)


def get_correlation_id() -> str:
    try:
        headers = activity.info().headers
        raw = headers.get("x-correlation-id")
        if raw:
            return raw[0].decode() if isinstance(raw[0], bytes) else str(raw[0])
    except RuntimeError:
        pass
    return str(uuid4())


@contextmanager
def activity_span(name: str) -> Iterator[str]:
    correlation_id = get_correlation_id()
    tracer = get_activity_tracer()
    with tracer.start_as_current_span(name) as span:
        span.set_attribute("activity.name", name)
        span.set_attribute("activity.type", "temporal")
        span.set_attribute("correlation_id", correlation_id)
        start = time.perf_counter()
        try:
            yield correlation_id
            duration_ms = (time.perf_counter() - start) * 1000
            activity_runs.add(1, {"activity": name, "status": "ok"})
            activity_duration.record(duration_ms, {"activity": name})
        except BaseException as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            activity_runs.add(1, {"activity": name, "status": "error"})
            activity_errors.add(1, {"activity": name, "error": type(exc).__qualname__})
            activity_duration.record(duration_ms, {"activity": name})
            span.record_exception(exc)
            raise
