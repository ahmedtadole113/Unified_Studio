"""OpenTelemetry distributed tracing + in-memory span ring buffer & Tempo OTLP export."""

import logging
import threading
import time
from collections import deque
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult

from core.config import settings

logger = logging.getLogger("ues.otel")

_SPAN_LOCK = threading.Lock()
_RECENT_SPANS: deque = deque(maxlen=250)


class RingBufferSpanExporter(SpanExporter):
    """Captures live OpenTelemetry spans into an in-memory buffer for instant UI trace waterfalls."""

    def export(self, spans: List[ReadableSpan]) -> SpanExportResult:
        with _SPAN_LOCK:
            for sp in spans:
                ctx = sp.get_span_context()
                parent = sp.parent
                duration_ms = round(((sp.end_time or 0) - (sp.start_time or 0)) / 1_000_000.0, 2)
                attrs = {k: str(v) for k, v in (sp.attributes or {}).items()}
                _RECENT_SPANS.appendleft(
                    {
                        "trace_id": format(ctx.trace_id, "032x"),
                        "span_id": format(ctx.span_id, "016x"),
                        "parent_span_id": format(parent.span_id, "016x") if parent else None,
                        "name": sp.name,
                        "service": attrs.get("service.name", "portal-backend"),
                        "domain": attrs.get("ues.domain", "platform"),
                        "status": sp.status.status_code.name if sp.status else "UNSET",
                        "duration_ms": duration_ms,
                        "start_time": int((sp.start_time or 0) / 1_000_000_000),
                        "attributes": attrs,
                    }
                )
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


class SafeOTLPSpanExporter(OTLPSpanExporter):
    """OTLP exporter that degrades quietly when Tempo is not started in Profile 1."""

    def export(self, spans: List[ReadableSpan]) -> SpanExportResult:
        try:
            return super().export(spans)
        except Exception as exc:
            logger.debug("Tempo OTLP export skipped (Tempo offline): %s", exc)
            return SpanExportResult.SUCCESS


_TRACER_INITIALIZED = False


def init_otel() -> trace.Tracer:
    global _TRACER_INITIALIZED
    if not _TRACER_INITIALIZED:
        resource = Resource.create({"service.name": "ues-portal-backend", "service.version": settings.APP_VERSION})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(RingBufferSpanExporter(), max_export_batch_size=32, schedule_delay_millis=1000))
        try:
            otlp_url = f"{settings.OTEL_EXPORTER_ENDPOINT.rstrip('/')}/v1/traces"
            provider.add_span_processor(BatchSpanProcessor(SafeOTLPSpanExporter(endpoint=otlp_url, timeout=1)))
        except Exception as exc:
            logger.debug("OTLP Tempo exporter init note: %s", exc)
        trace.set_tracer_provider(provider)
        _TRACER_INITIALIZED = True
    return trace.get_tracer("ues.control_plane")


@contextmanager
def traced_operation(name: str, domain: str = "platform", attributes: Optional[Dict[str, Any]] = None) -> Iterator[Any]:
    tracer = init_otel()
    with tracer.start_as_current_span(name) as span:
        span.set_attribute("ues.domain", domain)
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(str(k), str(v))
        yield span


def get_recent_traces(limit: int = 50) -> List[Dict[str, Any]]:
    with _SPAN_LOCK:
        return list(_RECENT_SPANS)[:limit]

