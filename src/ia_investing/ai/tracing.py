from __future__ import annotations

from opentelemetry import trace
from opentelemetry.context import Context


def span_context(
    *,
    run_id: str,
    case_id: str | None = None,
    workflow_id: str | None = None,
    capability: str,
    version: str,
) -> dict[str, str]:
    """Create correlated span attributes for an agent run."""
    attributes: dict[str, str] = {
        "agent.run_id": run_id,
        "agent.capability": capability,
        "agent.version": version,
    }
    if case_id:
        attributes["agent.case_id"] = case_id
    if workflow_id:
        attributes["agent.workflow_id"] = workflow_id
    return attributes


def inject_trace_context(headers: dict[str, str], trace_id: str) -> dict[str, str]:
    """Add a W3C traceparent header for downstream Temporal activity calls."""
    span = trace.get_current_span()
    span_ctx = span.get_span_context()

    if trace_id and span_ctx.trace_id:
        parent_trace_id = f"{span_ctx.trace_id:032x}"
    elif trace_id:
        parent_trace_id = trace_id.zfill(32)
    else:
        return headers

    parent_span_id = f"{span_ctx.span_id:016x}" if span_ctx.span_id else "0" * 16
    headers["traceparent"] = f"00-{parent_trace_id}-{parent_span_id}-01"
    return headers


def extract_trace_id(span_or_context: trace.Span | None = None) -> str | None:
    """Extract the trace_id from the given span or the current active span.

    Returns a 32-character hex string or *None* if no valid context is available.
    """
    if span_or_context is not None:
        span_ctx = span_or_context.get_span_context()
        if span_ctx is not None and span_ctx.trace_id:
            return f"{span_ctx.trace_id:032x}"
        return None

    span = trace.get_current_span()
    span_ctx = span.get_span_context()
    if span_ctx and span_ctx.trace_id:
        return f"{span_ctx.trace_id:032x}"
    return None


def inject_traceparent_into_context(trace_id: str) -> Context:
    """Return an OpenTelemetry Context carrying the given trace_id as the parent."""
    from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

    if not trace_id or len(trace_id) != 32:
        return Context()

    parent_ctx = SpanContext(
        trace_id=int(trace_id, 16),
        span_id=0,
        is_remote=True,
        trace_flags=TraceFlags(0x01),
    )
    return trace.set_span_in_context(NonRecordingSpan(parent_ctx))
