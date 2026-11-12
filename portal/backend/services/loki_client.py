"""Grafana Loki log aggregation client with live Docker container log fallback."""

import time
from typing import Any, Dict, List, Optional

import httpx

from core.config import settings
from services import docker_mgr


async def query_logs(
    logql: str = '{job="docker"}',
    container: Optional[str] = None,
    search: Optional[str] = None,
    minutes: int = 30,
    limit: int = 120,
) -> Dict[str, Any]:
    """Query Grafana Loki; if Loki is not started in current profile, query real Docker container logs directly."""
    end_ns = int(time.time() * 1_000_000_000)
    start_ns = end_ns - (minutes * 60 * 1_000_000_000)

    expr = logql
    if container and container != "all":
        expr = f'{{container_name="{container}"}}'
    if search:
        safe_search = search.replace('"', '\\"')
        expr = f'{expr} |= "{safe_search}"'

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{settings.LOKI_URL}/loki/api/v1/query_range",
                params={"query": expr, "start": str(start_ns), "end": str(end_ns), "limit": limit, "direction": "backward"},
            )
            if resp.status_code == 200:
                payload = resp.json()
                entries = []
                for stream in payload.get("data", {}).get("result", []):
                    labels = stream.get("stream", {})
                    for ts_ns, line in stream.get("values", []):
                        entries.append(
                            {
                                "timestamp": int(int(ts_ns) / 1_000_000_000),
                                "container": labels.get("container_name") or labels.get("job") or "loki",
                                "level": "ERROR" if ("error" in line.lower() or "fatal" in line.lower()) else ("WARN" if "warn" in line.lower() else "INFO"),
                                "message": line,
                            }
                        )
                if entries:
                    return {"source": "loki", "query": expr, "count": len(entries), "logs": entries[:limit]}
    except Exception:
        pass

    # Real Docker container logs fallback (reads actual running container stdout/stderr)
    targets = [container] if (container and container != "all") else [
        "portal-backend",
        "spark-processing",
        "airflow-scheduler",
        "airflow-webserver",
        "postgres-dw",
        "redpanda",
        "rabbitmq",
        "minio",
        "data-generator",
    ]
    entries: List[Dict[str, Any]] = []
    running = {c["name"] for c in docker_mgr.list_containers(all_containers=False, include_stats=False)}
    for cname in targets:
        if cname not in running:
            continue
        lines = docker_mgr.get_container_logs(cname, tail=max(20, limit // max(1, len(targets))))
        for line in reversed(lines):
            if search and search.lower() not in line.lower():
                continue
            ts_str, msg = (line.split(" ", 1) + [""])[:2] if "T" in line[:30] else ("", line)
            entries.append(
                {
                    "timestamp": ts_str or int(time.time()),
                    "container": cname,
                    "level": "ERROR" if ("error" in msg.lower() or "traceback" in msg.lower() or "fatal" in msg.lower()) else ("WARN" if "warn" in msg.lower() else "INFO"),
                    "message": msg,
                }
            )
            if len(entries) >= limit:
                break
        if len(entries) >= limit:
            break

    return {"source": "docker_logs", "query": expr, "count": len(entries), "logs": entries[:limit]}


async def push_log_to_loki(service: str, level: str, message: str, labels: Optional[Dict[str, str]] = None) -> bool:
    """Push structured platform/correlation logs directly into Loki when active."""
    stream_labels = {"job": "ues-control-plane", "container_name": service, "level": level}
    if labels:
        stream_labels.update(labels)
    payload = {
        "streams": [
            {
                "stream": stream_labels,
                "values": [[str(int(time.time() * 1_000_000_000)), message]],
            }
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.post(f"{settings.LOKI_URL}/loki/api/v1/push", json=payload)
            return resp.status_code in (200, 204)
    except Exception:
        return False

