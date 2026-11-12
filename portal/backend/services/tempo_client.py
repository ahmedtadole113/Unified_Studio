"""Grafana Tempo & OpenTelemetry distributed trace search client."""

from typing import Any, Dict, List

import httpx

from core.config import settings
from core.telemetry_otel import get_recent_traces


async def list_traces(limit: int = 40) -> Dict[str, Any]:
    """Query Grafana Tempo traces API and merge with live local OpenTelemetry span buffer."""
    tempo_traces: List[Dict[str, Any]] = []
    tempo_reachable = False
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            resp = await client.get(f"{settings.TEMPO_URL}/api/search", params={"limit": limit})
            if resp.status_code == 200:
                tempo_reachable = True
                data = resp.json()
                for t in data.get("traces", []):
                    tempo_traces.append(
                        {
                            "trace_id": t.get("traceID"),
                            "root_service": t.get("rootServiceName", "ues-portal-backend"),
                            "root_name": t.get("rootTraceName", "span"),
                            "duration_ms": t.get("durationMs", 0),
                            "start_time": t.get("startTimeUnixNano"),
                            "source": "tempo",
                        }
                    )
    except Exception:
        pass

    otel_spans = get_recent_traces(limit=limit)
    return {
        "tempo_reachable": tempo_reachable,
        "tempo_traces": tempo_traces,
        "otel_spans": otel_spans,
    }


async def get_trace_detail(trace_id: str) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.TEMPO_URL}/api/traces/{trace_id}")
            if resp.status_code == 200:
                return {"source": "tempo", "trace": resp.json()}
    except Exception:
        pass

    spans = [s for s in get_recent_traces(limit=250) if s["trace_id"] == trace_id]
    return {"source": "otel_buffer", "trace_id": trace_id, "spans": spans}

