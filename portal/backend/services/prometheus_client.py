"""Async Prometheus & Alertmanager client for live metrics, PromQL explorer, targets, rules, and alerts."""

import math
import time
from typing import Any, Dict, List, Optional

import httpx

from core.config import settings


async def _get_json(url: str, params: Optional[Dict[str, Any]] = None, timeout: float = 4.0) -> Optional[Dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        return None
    return None


async def prom_query(expr: str) -> Optional[float]:
    data = await _get_json(f"{settings.PROMETHEUS_URL}/api/v1/query", params={"query": expr})
    if not data or data.get("status") != "success":
        return None
    results = data.get("data", {}).get("result", [])
    if not results:
        return None
    try:
        val = float(results[0]["value"][1])
        return None if math.isnan(val) or math.isinf(val) else val
    except (KeyError, IndexError, ValueError, TypeError):
        return None


async def prom_query_raw(expr: str) -> Dict[str, Any]:
    data = await _get_json(f"{settings.PROMETHEUS_URL}/api/v1/query", params={"query": expr})
    if not data:
        return {"status": "error", "error": "Prometheus unreachable or not started in current profile"}
    return data


async def prom_range(expr: str, minutes: int = 15, step: str = "15s") -> List[Dict[str, Any]]:
    end = int(time.time())
    start = end - minutes * 60
    data = await _get_json(
        f"{settings.PROMETHEUS_URL}/api/v1/query_range",
        params={"query": expr, "start": start, "end": end, "step": step},
    )
    if not data or data.get("status") != "success":
        return []
    results = data.get("data", {}).get("result", [])
    if not results:
        return []
    points = []
    for ts, val_str in results[0].get("values", []):
        try:
            v = float(val_str)
            if not (math.isnan(v) or math.isinf(v)):
                points.append({"t": int(ts), "v": round(v, 4)})
        except (ValueError, TypeError):
            continue
    return points


async def get_observability_status() -> Dict[str, Any]:
    targets_raw = await _get_json(f"{settings.PROMETHEUS_URL}/api/v1/targets")
    rules_raw = await _get_json(f"{settings.PROMETHEUS_URL}/api/v1/rules")
    alerts_raw = await _get_json(f"{settings.PROMETHEUS_URL}/api/v1/alerts")
    am_raw = await _get_json(f"{settings.ALERTMANAGER_URL}/api/v2/alerts")

    prom_reachable = targets_raw is not None
    targets = [
        {
            "job": t.get("labels", {}).get("job", "unknown"),
            "instance": t.get("labels", {}).get("instance", ""),
            "health": t.get("health", "unknown"),
            "last_error": t.get("lastError", ""),
            "scrape_interval": t.get("scrapeInterval", ""),
        }
        for t in ((targets_raw or {}).get("data", {}).get("activeTargets", []))
    ]

    rules = []
    for g in ((rules_raw or {}).get("data", {}).get("groups", [])):
        for r in g.get("rules", []):
            rules.append(
                {
                    "name": r.get("name"),
                    "state": r.get("state"),
                    "severity": r.get("labels", {}).get("severity", "warning"),
                    "domain": r.get("labels", {}).get("domain", "general"),
                    "query": r.get("query"),
                    "summary": r.get("annotations", {}).get("summary", ""),
                }
            )

    alerts = [
        {
            "name": a.get("labels", {}).get("alertname", "Alert"),
            "severity": a.get("labels", {}).get("severity", "warning"),
            "domain": a.get("labels", {}).get("domain", "general"),
            "state": a.get("state", "firing"),
            "summary": a.get("annotations", {}).get("summary", ""),
            "description": a.get("annotations", {}).get("description", ""),
            "active_at": a.get("activeAt", ""),
        }
        for a in ((alerts_raw or {}).get("data", {}).get("alerts", []))
        if a.get("state") in ("firing", "pending")
    ]

    return {
        "prometheus_reachable": prom_reachable,
        "alertmanager_reachable": am_raw is not None,
        "targets": targets,
        "rules": rules,
        "alerts": alerts,
        "alertmanager_alerts": am_raw if isinstance(am_raw, list) else [],
    }

