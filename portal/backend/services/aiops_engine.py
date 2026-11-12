"""AIOps Engine: FAISS + TF-IDF Playbooks, Splunk SPL, Anomaly Detection, RCA, & Gemini Copilot."""

import json
import logging
import os
import re
import shlex
import statistics
import threading
import time
from collections import Counter, defaultdict, deque
from typing import Any, Dict, List, Optional

import faiss
import httpx
import numpy as np
from kafka import KafkaConsumer
from prometheus_client import Counter as PromCounter
from prometheus_client import Gauge, Histogram
from sklearn.feature_extraction.text import TfidfVectorizer

from core import database
from core.config import settings
from services import docker_mgr, k8s_mgr, prometheus_client, registry

logger = logging.getLogger("ues.aiops")

ANOMALIES_PROCESSED = PromCounter("aiops_anomalies_processed_total", "Total anomalies processed from Kafka/Telemetry")
KB_PLAYBOOKS_GAUGE = Gauge("aiops_kb_playbooks_count", "Number of playbooks loaded in FAISS KB")
GEMINI_REQUESTS = PromCounter("aiops_gemini_requests_total", "Total Google Gemini API calls", ["mode", "status"])
GEMINI_LATENCY = Histogram("aiops_gemini_latency_seconds", "Gemini API response latency seconds")

PLAYBOOKS: List[Dict[str, Any]] = [
    {"id": 1, "slug": "cpu-saturation", "domain": "infrastructure", "issue": "High CPU usage detected on server container runaway worker thread saturation", "remediation": "Inspect top CPU containers/processes, throttle noisy Spark or batch jobs, or enforce CPU quotas."},
    {"id": 2, "slug": "memory-leak-oom", "domain": "infrastructure", "issue": "High Memory usage detected approaching OOM limit OOMKilled heap leak", "remediation": "Stop idle containers via FinOps Profile Advisor, capture heap metrics, tune spark-defaults.conf, and restart service."},
    {"id": 3, "slug": "db-pool-exhaustion", "domain": "data_engineering", "issue": "Database PostgreSQL connection timeout ERROR pool exhausted max_connections", "remediation": "Inspect pg_stat_activity for idle-in-transaction sessions, terminate leaked connections, and verify Airflow DAG cursor cleanup."},
    {"id": 4, "slug": "airflow-spark-cascade", "domain": "data_engineering", "issue": "Airflow DAG failed Spark job executor killed task failure pipeline crash", "remediation": "Check airflow-scheduler health and Spark UI executor logs; recover scheduler/worker and re-trigger failed DAG run."},
    {"id": 5, "slug": "kafka-consumer-lag", "domain": "streaming", "issue": "Kafka Redpanda consumer lag high backlog offset behind partition stall", "remediation": "Check consumer group members, verify Spark Structured Streaming / AIOps consumer health, and scale partitions if needed."},
    {"id": 6, "slug": "rabbitmq-dlq-backlog", "domain": "streaming", "issue": "RabbitMQ queue backlog depth dead letter queue DLQ unacknowledged messages", "remediation": "Inspect RabbitMQ consumers, drain or replay DLQ messages, and verify downstream consumer availability."},
    {"id": 7, "slug": "k8s-crashloop", "domain": "kubernetes", "issue": "Kubernetes pod CrashLoopBackOff ImagePullBackOff OOMKilled restart loop scheduling failure", "remediation": "Inspect pod logs & K8s events, fix missing ConfigMap/Secret or memory limits, and delete/rollout failing pod."},
    {"id": 8, "slug": "http-500-burst", "domain": "availability", "issue": "Application throwing 500 ERROR codes failed requests burn rate availability breach", "remediation": "Enforce SLO release freeze, inspect tracebacks and recent deployment diffs, and initiate rollback if burn > 14.4x."},
    {"id": 9, "slug": "tail-latency-slo", "domain": "performance", "issue": "Tail latency SLO degradation detected p99 network latency downstream slowdown", "remediation": "Inspect Tempo/OTel trace waterfall, identify slow DB/S3/network hop, and clear active latency chaos or tune timeouts."},
    {"id": 10, "slug": "ai-model-drift", "domain": "ai_reliability", "issue": "AI model drift and train/serve skew detected output variance", "remediation": "Compare live feature distributions against baseline, verify feature parity, and fall back to deterministic rules."},
    {"id": 11, "slug": "token-gpu-cost-anomaly", "domain": "finops", "issue": "Token and GPU cost anomaly detected runaway retries spend", "remediation": "Cap agent retry budgets, inspect token inflation, and enable response caching."},
    {"id": 12, "slug": "nominal-operation", "domain": "baseline", "issue": "Normal operation nominal steady state message", "remediation": "No action required. Systems and pipelines are operating within SLO tolerances."},
]


class PlaybookKnowledgeBase:
    """In-memory FAISS L2 index over SRE, DE & AIOps remediation playbooks."""

    def __init__(self, playbooks: List[Dict[str, Any]]):
        self.playbooks = playbooks
        self.vectorizer = TfidfVectorizer()
        matrix = self.vectorizer.fit_transform([p["issue"] for p in playbooks]).toarray().astype(np.float32)
        self.index = faiss.IndexFlatL2(matrix.shape[1])
        self.index.add(matrix)

    @property
    def size(self) -> int:
        return self.index.ntotal

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        vec = self.vectorizer.transform([query]).toarray().astype(np.float32)
        distances, indices = self.index.search(vec, min(top_k, len(self.playbooks)))
        out = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            pb = self.playbooks[idx]
            sim = round(float(1.0 / (1.0 + dist)), 3)
            out.append({**pb, "similarity": sim, "distance": round(float(dist), 4)})
        return out

    def recommend_text(self, query: str) -> Dict[str, Any]:
        matches = self.search(query, top_k=1)
        if not matches:
            return {"remediation": "Investigate telemetry and escalate via runbook.", "runbook_slug": "http-500-burst", "domain": "general", "similarity": 0.0}
        top = matches[0]
        return {"remediation": top["remediation"], "runbook_slug": top["slug"], "domain": top["domain"], "similarity": top["similarity"]}


kb = PlaybookKnowledgeBase(PLAYBOOKS)
KB_PLAYBOOKS_GAUGE.set(kb.size)

_ANOMALIES_LOCK = threading.Lock()
_RECENT_ANOMALIES: deque = deque(maxlen=100)
_RAW_LOGS_LOCK = threading.Lock()
_RECENT_RAW_LOGS: deque = deque(maxlen=500)
_CONSUMERS_STARTED = False


def record_anomaly(anomaly: Dict[str, Any]) -> Dict[str, Any]:
    msg = anomaly.get("message") or anomaly.get("issue") or ""
    match = kb.recommend_text(msg)
    ANOMALIES_PROCESSED.inc()
    enriched = {
        "service": anomaly.get("service", "unknown"),
        "trace_id": anomaly.get("trace_id") or f"tr-{int(time.time()*1000)%1000000:06d}",
        "scenario": anomaly.get("scenario", "live_detection"),
        "issue": msg,
        "severity": anomaly.get("severity", "warning"),
        "metric_cpu": anomaly.get("cpu_usage"),
        "metric_mem": anomaly.get("mem_usage"),
        "latency_ms": anomaly.get("latency_ms"),
        "ai_recommendation": match["remediation"],
        "runbook_slug": match["runbook_slug"],
        "domain": match["domain"],
        "similarity": match["similarity"],
        "timestamp": anomaly.get("timestamp") or int(time.time()),
    }
    with _ANOMALIES_LOCK:
        _RECENT_ANOMALIES.appendleft(enriched)
    return enriched


def get_recent_anomalies(limit: int = 40) -> List[Dict[str, Any]]:
    with _ANOMALIES_LOCK:
        return list(_RECENT_ANOMALIES)[:limit]


def get_recent_raw_logs(limit: int = 200) -> List[Dict[str, Any]]:
    with _RAW_LOGS_LOCK:
        return list(_RECENT_RAW_LOGS)[:limit]


def _consume_kafka_loop(topic: str, is_anomaly: bool) -> None:
    """Resilient Kafka consumer that retries cleanly if Redpanda is stopped in Profile 1."""
    while True:
        consumer = None
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=[settings.KAFKA_BROKER],
                auto_offset_reset="latest",
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                consumer_timeout_ms=5000,
            )
            for message in consumer:
                val = message.value
                if not isinstance(val, dict):
                    continue
                if is_anomaly:
                    record_anomaly(val)
                else:
                    with _RAW_LOGS_LOCK:
                        _RECENT_RAW_LOGS.appendleft(val)
        except Exception:
            time.sleep(10)
        finally:
            if consumer:
                try:
                    consumer.close()
                except Exception:
                    pass


def start_kafka_consumers() -> None:
    global _CONSUMERS_STARTED
    if _CONSUMERS_STARTED:
        return
    _CONSUMERS_STARTED = True
    threading.Thread(target=_consume_kafka_loop, args=("anomalies_topic", True), daemon=True).start()
    threading.Thread(target=_consume_kafka_loop, args=("raw_app_logs", False), daemon=True).start()


# --- Splunk SPL Engine (preserved from ahmed_aiops) ---
def _to_num(val: Any) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _matches_search_clause(row: Dict[str, Any], search_expr: str) -> bool:
    if not search_expr.strip() or search_expr.strip() == "*":
        return True
    try:
        tokens = shlex.split(search_expr)
    except ValueError:
        tokens = search_expr.split()
    for tok in tokens:
        if tok.upper() in ("AND", "OR"):
            continue
        if "=" in tok and not tok.startswith("="):
            k, v = tok.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k == "index":
                continue
            row_val = str(row.get(k, ""))
            if v == "*":
                continue
            if "*" in v:
                if not re.match("^" + re.escape(v).replace("\\*", ".*") + "$", row_val, re.IGNORECASE):
                    return False
            elif row_val.lower() != v.lower():
                return False
        else:
            needle = tok.strip('"').strip("'").lower()
            if needle not in " ".join(str(val) for val in row.values()).lower():
                return False
    return True


def execute_spl(query: str) -> Dict[str, Any]:
    q = (query or "").strip() or "index=app_logs | head 25"
    parts = [p.strip() for p in q.split("|") if p.strip()]
    search_part = parts[0] if parts else "*"
    pipe_stages = parts[1:]

    use_anomalies = "index=anomalies" in search_part.lower()
    if use_anomalies:
        source = get_recent_anomalies(100)
    else:
        source = get_recent_raw_logs(300)
        if not source:
            # Synthesize structured log rows from live Docker container logs if Kafka raw logs empty
            for c in docker_mgr.list_containers(all_containers=False, include_stats=False)[:6]:
                for line in docker_mgr.get_container_logs(c["name"], tail=10):
                    source.append({
                        "service": c["name"],
                        "status": "ERROR" if "error" in line.lower() else ("WARN" if "warn" in line.lower() else "OK"),
                        "message": line,
                        "timestamp": int(time.time()),
                    })

    rows = [dict(r) for r in source if _matches_search_clause(r, search_part)]
    total_matched = len(rows)
    mode = "events"

    for stage in pipe_stages:
        tokens = stage.split(None, 1)
        cmd = tokens[0].lower()
        rest = tokens[1] if len(tokens) > 1 else ""
        if cmd == "stats":
            mode = "table"
            m_by = re.search(r"\bby\s+([a-zA-Z0-9_]+)\s*$", rest, re.IGNORECASE)
            by_field = m_by.group(1) if m_by else None
            agg_part = rest[: m_by.start()].strip() if m_by else rest.strip()
            aggs = [a.strip() for a in re.split(r"[\s,]+", agg_part) if a.strip()] or ["count"]
            groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for r in rows:
                groups[str(r.get(by_field, "unknown")) if by_field else "_all_"].append(r)
            res_rows = []
            for key, items in groups.items():
                rec: Dict[str, Any] = {by_field: key} if by_field else {}
                for agg in aggs:
                    low = agg.lower()
                    if low == "count":
                        rec["count"] = len(items)
                    else:
                        m_fn = re.match(r"^(avg|max|min|sum|count)\(([a-zA-Z0-9_]+)\)$", low)
                        if m_fn:
                            fn, fld = m_fn.groups()
                            vals = [v for v in (_to_num(it.get(fld)) for it in items) if v is not None]
                            rec[agg] = 0 if not vals else (len(vals) if fn == "count" else round(
                                statistics.mean(vals) if fn == "avg" else (max(vals) if fn == "max" else (min(vals) if fn == "min" else sum(vals))), 2
                            ))
                res_rows.append(rec)
            rows = res_rows
        elif cmd == "top":
            mode = "table"
            tokens_t = rest.split()
            limit = int(next((t for t in tokens_t if t.isdigit()), 10))
            field = next((t for t in tokens_t if not t.isdigit() and not t.startswith("limit=")), "service")
            counts = Counter(str(r.get(field, "unknown")) for r in rows)
            total = max(1, len(rows))
            rows = [{field: val, "count": cnt, "percent": round((cnt / total) * 100.0, 2)} for val, cnt in counts.most_common(limit)]
        elif cmd == "table":
            cols = [c.strip() for c in re.split(r"[\s,]+", rest) if c.strip()]
            if cols:
                rows = [{c: r.get(c, "") for c in cols} for r in rows]
                mode = "table"
        elif cmd == "head":
            limit = int(rest.strip()) if rest.strip().isdigit() else 20
            rows = rows[:limit]

    if mode == "events" and len(rows) > 50:
        rows = rows[:50]
    columns = list(rows[0].keys()) if rows else []
    return {
        "query": q,
        "index": "anomalies" if use_anomalies else "app_logs",
        "mode": mode,
        "total_matched": total_matched,
        "returned": len(rows),
        "columns": columns,
        "rows": rows,
    }


def detect_live_anomalies() -> List[Dict[str, Any]]:
    """Run deterministic & statistical anomaly detection over real container, service, and K8s state."""
    detected: List[Dict[str, Any]] = []
    services = registry.get_cached_registry()
    for s in services:
        if s["status"] == "unavailable" and s["docker_exists"]:
            detected.append({
                "service": s["service_id"],
                "severity": "critical" if s["criticality"] == "critical" else "warning",
                "scenario": "service_down",
                "issue": f"Service '{s['service_name']}' container '{s['container_name']}' is {s['docker_status']} ({s['probe_detail']})",
                "cpu_usage": s["cpu_utilization_pct"],
                "mem_usage": s["memory_utilization_mb"],
            })
        elif s["cpu_utilization_pct"] > 80.0:
            detected.append({
                "service": s["service_id"],
                "severity": "warning",
                "scenario": "cpu_saturation",
                "issue": f"High CPU usage detected on {s['container_name']}: {s['cpu_utilization_pct']}%",
                "cpu_usage": s["cpu_utilization_pct"],
                "mem_usage": s["memory_utilization_mb"],
            })
        elif s["memory_utilization_pct"] > 85.0 or s.get("oom_killed"):
            detected.append({
                "service": s["service_id"],
                "severity": "critical",
                "scenario": "memory_pressure",
                "issue": f"High Memory usage / OOM risk on {s['container_name']}: {s['memory_utilization_mb']}MB ({s['memory_utilization_pct']}%)",
                "cpu_usage": s["cpu_utilization_pct"],
                "mem_usage": s["memory_utilization_mb"],
            })

    k8s = k8s_mgr.get_cluster_overview()
    if k8s.get("connected"):
        for pod_ref in k8s["summary"].get("crashloop_pods", []):
            detected.append({
                "service": f"k8s:{pod_ref}",
                "severity": "critical",
                "scenario": "k8s_crashloop",
                "issue": f"Kubernetes pod CrashLoopBackOff detected: {pod_ref}",
            })
        for pod_ref in k8s["summary"].get("oom_killed_pods", []):
            detected.append({
                "service": f"k8s:{pod_ref}",
                "severity": "critical",
                "scenario": "k8s_oomkilled",
                "issue": f"Kubernetes pod OOMKilled detected: {pod_ref}",
            })

    out = []
    for d in detected:
        match = kb.recommend_text(d["issue"])
        out.append({**d, "ai_recommendation": match["remediation"], "runbook_slug": match["runbook_slug"], "domain": match["domain"], "similarity": match["similarity"], "timestamp": int(time.time())})
    return out + get_recent_anomalies(25)


async def get_aiops_insights() -> Dict[str, Any]:
    """Unified AIOps summary: anomalies, correlated alerts, performance/capacity recommendations, & log summary."""
    anomalies = detect_live_anomalies()
    obs = await prometheus_client.get_observability_status()
    incidents = database.get_incidents(limit=20)
    containers = docker_mgr.list_containers(all_containers=True, include_stats=True)

    # Predictive & performance recommendations grounded in real measurements
    recommendations: List[Dict[str, Any]] = []
    running = [c for c in containers if c.get("running")]
    total_mem = sum(c.get("memory_mb", 0.0) for c in running)
    if total_mem > 4200:
        recommendations.append({
            "category": "Capacity / M4 8GB",
            "priority": "high",
            "title": "Container working set approaching 5 GB M4 ceiling",
            "detail": f"Measured container RAM is {round(total_mem, 1)} MB. Consider stopping idle DE/SRE profiles.",
        })
    for c in running:
        if c["memory_percent"] > 80.0:
            recommendations.append({
                "category": "Memory Tuning",
                "priority": "high",
                "title": f"{c['name']} memory at {c['memory_percent']}% of container limit",
                "detail": f"Using {c['memory_mb']} / {c['memory_limit_mb']} MB. Increase limit or tune JVM/buffer configuration.",
            })
        if c["name"] not in ("portal-backend", "portal-frontend", "prometheus") and c["cpu_percent"] < 0.2 and c["memory_mb"] > 150:
            recommendations.append({
                "category": "FinOps Idle Optimization",
                "priority": "medium",
                "title": f"Idle heavy service '{c['name']}'",
                "detail": f"Consuming {c['memory_mb']} MB RAM at {c['cpu_percent']}% CPU. Safe to pause when not running labs.",
            })
    if not recommendations:
        recommendations.append({
            "category": "System Posture",
            "priority": "low",
            "title": "All running services are well within Apple Silicon M4 8GB thresholds",
            "detail": f"{len(running)} containers active, total measured memory {round(total_mem, 1)} MB.",
        })

    # Alert correlation summary
    correlations = []
    for inc in incidents:
        if inc.get("pipeline_id") or inc.get("service_id") or inc.get("k8s_pod"):
            correlations.append({
                "incident_id": inc["id"],
                "title": inc["title"],
                "severity": inc["severity"],
                "status": inc["status"],
                "pipeline_id": inc.get("pipeline_id"),
                "service_id": inc.get("service_id"),
                "k8s_pod": inc.get("k8s_pod"),
                "rca_summary": inc.get("ai_rca") or inc.get("summary"),
                "remediation": inc.get("remediation"),
            })

    return {
        "anomalies": anomalies[:40],
        "firing_alerts": obs["alerts"],
        "correlated_incidents": correlations[:15],
        "recommendations": recommendations,
        "playbooks_count": kb.size,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "gemini_model": settings.GEMINI_MODEL,
    }


async def ask_copilot(prompt: str, mode: str = "copilot", service: str = "platform", api_key: Optional[str] = None) -> Dict[str, Any]:
    """Context-aware Gemini AI Copilot with deterministic FAISS/DE fallback when API key is not set."""
    key = (api_key or settings.GEMINI_API_KEY or "").strip()
    if not key:
        matches = kb.search(prompt, top_k=2)
        best = matches[0] if matches else {}
        fallback_md = (
            f"### Unified Engineering Studio Local AI Helper (`{mode.upper()}` / `{service}`)\n\n"
            f"**Top Matched Remediation Playbook:** `{best.get('slug', 'general')}` (confidence `{best.get('similarity', 0)}`)\n\n"
            f"- **Recommendation:** {best.get('remediation', 'Inspect live logs, Prometheus targets, and service registry health.')}\n"
            f"- **Query Context:** *{prompt[:200]}*\n\n"
            f"> Configure a Google Gemini API Key in Studio Settings or `.env` (`GEMINI_API_KEY`) to enable full generative RCA & code synthesis."
        )
        return {"status": "success", "response": fallback_md, "is_mock": True, "provider": "local-faiss"}

    sys_instruction = (
        "You are a Principal Platform Engineer, Data Engineering Architect (Spark 4.2, Delta 4.0, Iceberg, Airflow, PostgreSQL, MinIO, Redpanda, RabbitMQ), "
        "and Staff SRE/AIOps Architect (Prometheus, Grafana, Loki, Tempo, Kubernetes, SLO/Error Budgets). "
        "Provide concise, evidence-driven, production-grade guidance."
    )
    model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"
    endpoints = [
        f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
    ]
    payload = {
        "systemInstruction": {"parts": [{"text": sys_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": f"Domain/Service: {service}\nMode: {mode}\n\n{prompt}"}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
    }

    t0 = time.time()
    last_err = ""
    async with httpx.AsyncClient(timeout=25.0) as client:
        for url in endpoints:
            try:
                resp = await client.post(url, headers={"Content-Type": "application/json", "x-goog-api-key": key}, json=payload)
                if resp.status_code == 200:
                    GEMINI_LATENCY.observe(time.time() - t0)
                    GEMINI_REQUESTS.labels(mode=mode, status="ok").inc()
                    cands = resp.json().get("candidates", [])
                    parts = cands[0].get("content", {}).get("parts", []) if cands else []
                    text = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
                    if text:
                        return {"status": "success", "response": text, "is_mock": False, "provider": "gemini"}
                last_err = f"HTTP {resp.status_code}: {resp.text[:180]}"
            except Exception as exc:
                last_err = str(exc)

    GEMINI_REQUESTS.labels(mode=mode, status="error").inc()
    matches = kb.search(prompt, top_k=1)
    best = matches[0] if matches else {}
    return {
        "status": "error",
        "response": f"Gemini call failed ({last_err}). Local FAISS guidance:\n\n- **Playbook `{best.get('slug')}`:** {best.get('remediation')}",
        "is_mock": True,
        "provider": "local-faiss-fallback",
    }

