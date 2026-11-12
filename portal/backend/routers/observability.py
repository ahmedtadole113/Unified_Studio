"""Centralized Observability Router (`/api/v1/metrics`, `/api/v1/logs`, `/api/v1/traces`)."""

from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core import security
from services import aiops_engine, loki_client, prometheus_client, tempo_client

router = APIRouter(tags=["Observability"])


@router.get("/api/v1/metrics/overview")
async def metrics_overview(user: Dict[str, str] = Depends(security.get_current_user)):
    obs = await prometheus_client.get_observability_status()
    cpu_series = await prometheus_client.prom_range("sum(ues_container_cpu_percent)", minutes=15, step="15s")
    mem_series = await prometheus_client.prom_range("sum(ues_container_memory_mb)", minutes=15, step="15s")
    app_cpu = await prometheus_client.prom_range("app_cpu_usage_percent", minutes=15, step="15s")
    return {
        **obs,
        "series": {
            "total_container_cpu": cpu_series,
            "total_container_mem_mb": mem_series,
            "app_cpu_percent": app_cpu,
        },
        "grafana_dashboards": [
            {"id": "ues-platform-overview", "title": "01. Platform Overview", "url": "/services/monitoring/d/ues-platform-overview"},
            {"id": "ues-infra-health", "title": "02. Infrastructure Health", "url": "/services/monitoring/d/ues-infra-health"},
            {"id": "ues-k8s-cluster", "title": "03. Kubernetes Cluster", "url": "/services/monitoring/d/ues-k8s-cluster"},
            {"id": "ues-spark-perf", "title": "04. Spark Performance", "url": "/services/monitoring/d/ues-spark-perf"},
            {"id": "ues-airflow-rel", "title": "05. Airflow Reliability", "url": "/services/monitoring/d/ues-airflow-rel"},
            {"id": "ues-kafka-rabbit", "title": "06. Kafka & RabbitMQ", "url": "/services/monitoring/d/ues-kafka-rabbit"},
            {"id": "ues-db-perf", "title": "07. Database Performance", "url": "/services/monitoring/d/ues-db-perf"},
            {"id": "ues-slo-budgets", "title": "08. SLO & Error Budgets", "url": "/services/monitoring/d/ues-slo-budgets"},
        ],
    }


@router.get("/api/v1/metrics/promql")
async def promql_query(expr: str, user: Dict[str, str] = Depends(security.get_current_user)):
    if not expr.strip():
        raise HTTPException(status_code=400, detail="PromQL expression required")
    return await prometheus_client.prom_query_raw(expr)


@router.get("/api/v1/logs/search")
async def search_logs(
    container: Optional[str] = "all",
    search: Optional[str] = None,
    minutes: int = 30,
    limit: int = 120,
    user: Dict[str, str] = Depends(security.get_current_user),
):
    return await loki_client.query_logs(container=container, search=search, minutes=minutes, limit=limit)


@router.get("/api/v1/logs/spl")
def run_spl_query(q: str = "index=app_logs | head 25", user: Dict[str, str] = Depends(security.get_current_user)):
    return aiops_engine.execute_spl(q)


@router.get("/api/v1/traces")
async def list_traces(limit: int = 40, user: Dict[str, str] = Depends(security.get_current_user)):
    return await tempo_client.list_traces(limit=limit)


@router.get("/api/v1/traces/{trace_id}")
async def trace_detail(trace_id: str, user: Dict[str, str] = Depends(security.get_current_user)):
    return await tempo_client.get_trace_detail(trace_id)

